"""Provides the ezviz DataUpdateCoordinator."""
from datetime import timedelta
import logging

from async_timeout import timeout
from .http_client import EzvizHttpClient
import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EzvizDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Ezviz data."""

    def __init__(self, hass: HomeAssistant, *, api: EzvizHttpClient, api_timeout: int) -> None:
        """Initialize global Ezviz data updater."""
        self.ezviz_client = api
        self._api_timeout = api_timeout
        update_interval = timedelta(seconds=30)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    def _update_data(self) -> dict:
        """Fetch Ezviz switchable devices data.
        
        This method retrieves all devices with switchable features from the EZVIZ API.
        It processes all types of devices and their switchable entities, not limited to
        specific model prefixes. Each device can have multiple switchable entities which
        are all captured and stored.
        """

        devices = {}
        switches = self.ezviz_client._api_get_pagelist(page_filter="SWITCH")
        _LOGGER.debug("Found %d total devices from API", len(switches.get('deviceInfos', [])))
        
        for device in switches['deviceInfos']:
            # Process all entities for each device, not just the first one
            entities = []
            device_serial = device['deviceSerial']
            
            if device_serial in switches['SWITCH']:
                for entity in switches['SWITCH'][device_serial]:
                    entity_data = {
                        'enable': entity['enable'],
                        'switch_type': int(entity['type'])
                    }
                    entities.append(entity_data)
                
                # If we have entities, store the device with its entities
                if entities:
                    # For backward compatibility, store the first entity's data at device level
                    device['enable'] = entities[0]['enable']
                    device['switch_type'] = entities[0]['switch_type']
                    device['entities'] = entities
                    
                    # Include all devices with switchable entities - supports all EZVIZ device types
                    devices[device_serial] = device
                    _LOGGER.debug("Added device %s with %d entities (types: %s)", 
                                device_serial, len(entities), 
                                [e['switch_type'] for e in entities])

        _LOGGER.info("Discovered %d switchable devices (all EZVIZ device types with switchable features)", len(devices))
        return devices

    async def _async_update_data(self) -> dict:
        """Fetch data from Ezviz."""
        try:
            async with timeout(self._api_timeout):
                return await self.hass.async_add_executor_job(self._update_data)

        except (requests.exceptions.RequestException, Exception) as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error