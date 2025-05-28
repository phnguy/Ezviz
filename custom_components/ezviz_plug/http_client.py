"""HTTP client for Ezviz API."""
import logging
import requests
import json
from typing import Any, Dict, Optional, List
from .const import EU_URL, CONF_SESSION_ID, CONF_RFSESSION_ID

_LOGGER = logging.getLogger(__name__)

class EzvizHttpClient:
    """HTTP client for Ezviz API."""

    def __init__(
        self, 
        email: str = "",
        password: str = "",
        api_url: str = EU_URL,
        timeout: int = 30,
        session_id: str = None,
        rf_session_id: str = None
    ) -> None:
        """Initialize the client."""
        self.email = email
        self.password = password
        self.api_url = api_url
        self.timeout = timeout
        self.session_id = session_id
        self.rf_session_id = rf_session_id
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
        })

    def login(self) -> Dict[str, Any]:
        """Login to the Ezviz API and return auth tokens."""
        url = f"https://{self.api_url}/v3/users/login/v5"
        data = {
            "account": self.email,
            "password": self.password,
            "featureCode": "92c579faa0902cbfcfcc4fc004ef67e7"
        }

        try:
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("meta", {}).get("code") != 200:
                error_msg = response_data.get("meta", {}).get("message", "Unknown error")
                _LOGGER.error("Login failed: %s", error_msg)
                raise Exception(f"Login failed: {error_msg}")

            # Extract session tokens
            self.session_id = response_data["data"]["sessionId"]
            self.rf_session_id = response_data["data"]["rfSessionId"]
            
            # Update session headers with authentication tokens
            self.session.headers.update({
                "sessionId": self.session_id,
                "rfSessionId": self.rf_session_id
            })

            return {
                CONF_SESSION_ID: self.session_id,
                CONF_RFSESSION_ID: self.rf_session_id,
                "api_url": self.api_url
            }
        except requests.RequestException as e:
            _LOGGER.error("Error during login: %s", e)
            raise

    def _api_get_pagelist(self, page_filter: str = None) -> Dict[str, Any]:
        """Get pagelist data from the API - equivalent to SDK method."""
        if not self.session_id or not self.rf_session_id:
            _LOGGER.error("Authentication required. Call login() first.")
            raise Exception("Authentication required")

        url = f"https://{self.api_url}/v3/userdevices/v1/devices/pagelist"
        params = {
            "filter": page_filter or "",
            "pageSize": 50,  # Max page size
            "pageStart": 0,
        }

        try:
            response = self.session.post(url, json=params, timeout=self.timeout)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("meta", {}).get("code") != 200:
                error_msg = response_data.get("meta", {}).get("message", "Unknown error")
                _LOGGER.error("Error getting pagelist: %s", error_msg)
                raise Exception(f"API error: {error_msg}")

            # Transform the response to match the format expected by existing code
            result = {
                "deviceInfos": response_data.get("data", {}).get("deviceInfos", [])
            }
            
            # Add the SWITCH section if filter is SWITCH
            if page_filter == "SWITCH":
                result["SWITCH"] = {}
                for device in response_data.get("data", {}).get("switchStatusInfos", []):
                    device_serial = device.get("deviceSerial")
                    if device_serial:
                        if device_serial not in result["SWITCH"]:
                            result["SWITCH"][device_serial] = []
                        # Add switch entities to the device
                        for switch in device.get("switchs", []):
                            result["SWITCH"][device_serial].append(switch)

            return result
        except requests.RequestException as e:
            _LOGGER.error("Error getting pagelist: %s", e)
            raise

    def switch_status(self, serial: str, switch_type: int, enable: int) -> bool:
        """Set switch status for a device."""
        if not self.session_id or not self.rf_session_id:
            _LOGGER.error("Authentication required. Call login() first.")
            return False

        url = f"https://{self.api_url}/v3/userdevices/v1/devices/switchStatus"
        data = {
            "deviceSerial": serial,
            "enable": enable,
            "type": switch_type
        }

        try:
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("meta", {}).get("code") != 200:
                error_msg = response_data.get("meta", {}).get("message", "Unknown error")
                _LOGGER.error("Error setting switch status: %s", error_msg)
                return False

            return True
        except requests.RequestException as e:
            _LOGGER.error("Error setting switch status: %s", e)
            return False

    def close_session(self) -> None:
        """Close the session."""
        if self.session:
            self.session.close()