"""Doorbell review client for Ezviz API."""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from .http_client import EzvizHttpClient
from .const import DOORBELL_ALARM_TYPE, DOORBELL_DEFAULT_PAGE_SIZE, DOORBELL_MAX_HISTORY_DAYS

_LOGGER = logging.getLogger(__name__)


class EzvizDoorbellClient:
    """Specialized client for Ezviz doorbell review operations.
    
    This class handles doorbell-specific functionality such as:
    - Retrieving visitor events and records
    - Getting doorbell media (images/videos)
    - Managing doorbell event history
    - Handling doorbell notifications
    
    It extends the base EzvizHttpClient functionality with doorbell-specific methods.
    """

    def __init__(self, http_client: EzvizHttpClient) -> None:
        """Initialize the doorbell client.
        
        Args:
            http_client: An authenticated EzvizHttpClient instance
        """
        self.http_client = http_client
        self._logger = _LOGGER

    def get_doorbell_events(
        self, 
        device_serial: str, 
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page_size: int = DOORBELL_DEFAULT_PAGE_SIZE,
        page_start: int = 0
    ) -> Dict[str, Any]:
        """Get doorbell events for a specific device.
        
        Args:
            device_serial: The serial number of the doorbell device
            start_time: Start time for event query (defaults to 24 hours ago)
            end_time: End time for event query (defaults to now)
            page_size: Number of events per page
            page_start: Starting page for pagination
            
        Returns:
            Dict containing doorbell events data
        """
        if not self.http_client.session_id or not self.http_client.rf_session_id:
            self._logger.error("Authentication required. Call login() first.")
            raise Exception("Authentication required")

        # Default time range: last 24 hours
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(hours=24)

        url = f"https://{self.http_client.api_url}/v3/alarm/device/history"
        params = {
            "deviceSerial": device_serial,
            "startTime": int(start_time.timestamp() * 1000),  # Convert to milliseconds
            "endTime": int(end_time.timestamp() * 1000),
            "pageSize": page_size,
            "pageStart": page_start,
            "alarmType": DOORBELL_ALARM_TYPE  # Doorbell event type
        }

        try:
            response = self.http_client.session.post(url, json=params, timeout=self.http_client.timeout)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("meta", {}).get("code") != 200:
                error_msg = response_data.get("meta", {}).get("message", "Unknown error")
                self._logger.error("Error getting doorbell events: %s", error_msg)
                raise Exception(f"API error: {error_msg}")

            return response_data.get("data", {})

        except Exception as e:
            self._logger.error("Error getting doorbell events: %s", e)
            raise

    def get_visitor_image(self, device_serial: str, alarm_id: str) -> Optional[bytes]:
        """Get visitor image for a specific doorbell event.
        
        Args:
            device_serial: The serial number of the doorbell device
            alarm_id: The alarm/event ID to get the image for
            
        Returns:
            Image data as bytes, or None if not available
        """
        if not self.http_client.session_id or not self.http_client.rf_session_id:
            self._logger.error("Authentication required. Call login() first.")
            raise Exception("Authentication required")

        url = f"https://{self.http_client.api_url}/v3/alarm/device/pic"
        params = {
            "deviceSerial": device_serial,
            "alarmId": alarm_id
        }

        try:
            response = self.http_client.session.post(url, json=params, timeout=self.http_client.timeout)
            response.raise_for_status()
            
            # Check if response is JSON (error) or binary (image)
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                response_data = response.json()
                if response_data.get("meta", {}).get("code") != 200:
                    error_msg = response_data.get("meta", {}).get("message", "Unknown error")
                    self._logger.error("Error getting visitor image: %s", error_msg)
                    return None
            else:
                # Return image data
                return response.content

        except Exception as e:
            self._logger.error("Error getting visitor image: %s", e)
            raise

    def get_doorbell_summary(self, device_serial: str, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get doorbell activity summary for a specific date.
        
        Args:
            device_serial: The serial number of the doorbell device
            date: Date to get summary for (defaults to today)
            
        Returns:
            Dict containing doorbell activity summary
        """
        if not self.http_client.session_id or not self.http_client.rf_session_id:
            self._logger.error("Authentication required. Call login() first.")
            raise Exception("Authentication required")

        if date is None:
            date = datetime.now()

        # Get start and end of the day
        start_time = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = date.replace(hour=23, minute=59, second=59, microsecond=999999)

        try:
            events = self.get_doorbell_events(
                device_serial=device_serial,
                start_time=start_time,
                end_time=end_time,
                page_size=100  # Get more events for summary
            )

            # Create summary from events
            total_events = len(events.get("alarms", []))
            
            summary = {
                "date": date.strftime("%Y-%m-%d"),
                "total_events": total_events,
                "device_serial": device_serial,
                "events": events.get("alarms", [])
            }

            return summary

        except Exception as e:
            self._logger.error("Error getting doorbell summary: %s", e)
            raise

    def mark_event_as_viewed(self, device_serial: str, alarm_id: str) -> bool:
        """Mark a doorbell event as viewed.
        
        Args:
            device_serial: The serial number of the doorbell device
            alarm_id: The alarm/event ID to mark as viewed
            
        Returns:
            True if successful, False otherwise
        """
        if not self.http_client.session_id or not self.http_client.rf_session_id:
            self._logger.error("Authentication required. Call login() first.")
            return False

        url = f"https://{self.http_client.api_url}/v3/alarm/device/read"
        params = {
            "deviceSerial": device_serial,
            "alarmId": alarm_id
        }

        try:
            response = self.http_client.session.post(url, json=params, timeout=self.http_client.timeout)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("meta", {}).get("code") != 200:
                error_msg = response_data.get("meta", {}).get("message", "Unknown error")
                self._logger.error("Error marking event as viewed: %s", error_msg)
                return False

            return True

        except Exception as e:
            self._logger.error("Error marking event as viewed: %s", e)
            return False

    def get_doorbell_config(self, device_serial: str) -> Dict[str, Any]:
        """Get doorbell configuration settings.
        
        Args:
            device_serial: The serial number of the doorbell device
            
        Returns:
            Dict containing doorbell configuration
        """
        if not self.http_client.session_id or not self.http_client.rf_session_id:
            self._logger.error("Authentication required. Call login() first.")
            raise Exception("Authentication required")

        url = f"https://{self.http_client.api_url}/v3/devices/{device_serial}/doorbell/config"
        
        try:
            response = self.http_client.session.get(url, timeout=self.http_client.timeout)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("meta", {}).get("code") != 200:
                error_msg = response_data.get("meta", {}).get("message", "Unknown error")
                self._logger.error("Error getting doorbell config: %s", error_msg)
                raise Exception(f"API error: {error_msg}")

            return response_data.get("data", {})

        except Exception as e:
            self._logger.error("Error getting doorbell config: %s", e)
            raise
            
    def open_gate(self, device_serial: str) -> bool:
        """Open the gate associated with a doorbell device.
        
        Args:
            device_serial: The serial number of the doorbell device
            
        Returns:
            True if successful, False otherwise
        """
        if not self.http_client.session_id or not self.http_client.rf_session_id:
            self._logger.error("Authentication required. Call login() first.")
            return False

        url = f"https://{self.http_client.api_url}/v3/devices/{device_serial}/doorbell/openDoor"
        
        try:
            response = self.http_client.session.post(url, timeout=self.http_client.timeout)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("meta", {}).get("code") != 200:
                error_msg = response_data.get("meta", {}).get("message", "Unknown error")
                self._logger.error("Error opening gate: %s", error_msg)
                return False

            self._logger.info("Gate opened successfully for device %s", device_serial)
            return True

        except Exception as e:
            self._logger.error("Error opening gate: %s", e)
            return False