"""Support for EzvizSwitch."""
from __future__ import annotations

import logging
from typing import Any, Dict
from datetime import datetime, timedelta
import voluptuous as vol

try:
    from homeassistant.components.switch import SwitchEntity
except ImportError:
    from homeassistant.components.switch import SwitchDevice as SwitchEntity
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant import core

from pyezviz import client
from pyezviz.exceptions import (
    AuthTestResultFailed,
    EzvizAuthVerificationCode,
    InvalidHost,
    InvalidURL,
    HTTPError,
    PyEzvizError,
)

from pyezviz.constants import (DeviceSwitchType)
from .const import DOMAIN
from .coordinator import EzvizDataUpdateCoordinator

SCAN_INTERVAL = timedelta(seconds=5)
_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_EMAIL): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


async def async_unload_entry(hass, config_entry):
    _LOGGER.debug(f"async_unload_entry {DOMAIN}: {config_entry}")

    return True


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Ezviz switchable devices."""

    _LOGGER.debug('calling setup_platform')

    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    ezvizClient = client.EzvizClient(email, password)

    try:
        auth_data = await hass.async_add_executor_job(ezvizClient.login)
    except (InvalidHost, InvalidURL, HTTPError, PyEzvizError) as error:
        _LOGGER.exception('Invalid response from API: %s', error)
    except EzvizAuthVerificationCode:
        _LOGGER.exception('MFA Required')
    except (Exception) as error:
        _LOGGER.exception('Unexpected exception: %s', error)

    coordinator = EzvizDataUpdateCoordinator(hass, api=ezvizClient, api_timeout=10)

    # Add devices
    entities = []
    devices = await coordinator._async_update_data();
    for key, device in devices.items():
        entities.append(Ezvizswitch(device, ezvizClient))

    add_entities(entities)

    # Do not close the client session as it's needed by the entities
    # _LOGGER.info('Closing the Client session.')
    # ezvizClient.close_session()


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    """Set up Ezviz switch based on a config entry."""

    email = hass.data[DOMAIN][entry.entry_id][CONF_EMAIL]
    password = hass.data[DOMAIN][entry.entry_id][CONF_PASSWORD]
    ezvizClient = client.EzvizClient(email, password)

    try:
        auth_data = await hass.async_add_executor_job(ezvizClient.login)
    except (InvalidHost, InvalidURL, HTTPError, PyEzvizError) as error:
        _LOGGER.exception('Invalid response from API: %s', error)
    except EzvizAuthVerificationCode:
        _LOGGER.exception('MFA Required')
    except (Exception) as error:
        _LOGGER.exception('Unexpected exception: %s', error)

    coordinator = EzvizDataUpdateCoordinator(hass, api=ezvizClient, api_timeout=10)

    # Add devices
    entities = []
    devices = await coordinator._async_update_data();
    for key, device in devices.items():
        entities.append(Ezvizswitch(device, ezvizClient))

    async_add_entities(entities)

    # Do not close the client session as it's needed by the entities
    # _LOGGER.debug('Closing the Client session.')
    # ezvizClient.close_session()


class Ezvizswitch(SwitchEntity, RestoreEntity):
    """Representation of Ezviz Switchable Device Entity."""

    def __init__(self, switch, ezvizClient) -> None:
        """Initialize the Ezviz device."""

        self._state = None
        self._last_run_success = None
        self._last_pressed: datetime | None = None
        self._switch = switch
        self._ezviz_client = ezvizClient

    async def async_added_to_hass(self):
        """Run when entity about to be added."""

        _LOGGER.info('async_added_to_hass called')

        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state == "on"

    def turn_on(self, **kwargs) -> None:
        """Turn device on."""

        _LOGGER.debug('Turning on %s (current state is: %s cloud: %s)', self._switch['name'], self._state,
                     self._switch['enable'])

        # Use the actual device switch_type instead of hardcoding to DeviceSwitchType.PLUG
        switch_type = self._switch.get('switch_type', DeviceSwitchType.PLUG.value)  # Default to PLUG if not found for backward compatibility
        _LOGGER.debug('Using switch type: %s for device: %s', switch_type, self._switch['name'])
        
        if self._ezviz_client.switch_status(self._switch["deviceSerial"], switch_type, 1):
            self._state = True
            self._switch['enable'] = True
            self._last_pressed = dt_util.utcnow()
            self._last_run_success = True
        else:
            self._last_run_success = False

    def turn_off(self, **kwargs) -> None:
        """Turn device off."""
        _LOGGER.debug('Turning off %s (current state is: %s cloud: %s)', self._switch['name'], self._state,
                     self._switch['enable'])

        # Use the actual device switch_type instead of hardcoding to DeviceSwitchType.PLUG
        switch_type = self._switch.get('switch_type', DeviceSwitchType.PLUG.value)  # Default to PLUG if not found for backward compatibility
        _LOGGER.debug('Using switch type: %s for device: %s', switch_type, self._switch['name'])
        
        if self._ezviz_client.switch_status(self._switch["deviceSerial"], switch_type, 0):
            self._state = False
            self._switch['enable'] = False
            self._last_pressed = dt_util.utcnow()
            self._last_run_success = True
        else:
            self._last_run_success = False

    def _fetch_switch_data(self):
        """Fetch switch data synchronously."""
        return self._ezviz_client._api_get_pagelist(page_filter="SWITCH")
    
    async def async_update(self):
        """Update the entity."""
        _LOGGER.debug("calling update method.")

        try:
            # Use async_add_executor_job to avoid blocking the event loop
            switches = await self.hass.async_add_executor_job(self._fetch_switch_data)
            
            # Process the data similar to coordinator._update_data
            for device in switches['deviceInfos']:
                if device['deviceSerial'] == self._switch['deviceSerial']:
                    # Process all entities for the device
                    entities = []
                    device_serial = device['deviceSerial']
                    
                    if device_serial in switches['SWITCH']:
                        for entity in switches['SWITCH'][device_serial]:
                            entity_data = {
                                'enable': entity['enable'],
                                'switch_type': int(entity['type'])
                            }
                            entities.append(entity_data)
                        
                        # Store entity information
                        if entities:
                            # For backward compatibility, use the first entity's data
                            device['enable'] = entities[0]['enable']
                            device['switch_type'] = entities[0]['switch_type']
                            device['entities'] = entities
                    
                    self._switch = device
                    break
        except Exception as ex:
            _LOGGER.error("Error updating entity: %s", ex)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""

        if not isinstance(self._state, bool):
            self._state = (True if self._switch['enable'] == 1 else False)

        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return False if self._switch['status'] == 2 else True

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._switch['deviceSerial']

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._switch['name']

    def last_pressed(self) -> str:
        if self._last_pressed is None:
            return ''
        return self._last_pressed.isoformat()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attributes = {
            "last_run_success": self._last_run_success,
            "last_pressed": self.last_pressed()
        }
        
        # Include the switch type in the attributes if available
        if 'switch_type' in self._switch:
            attributes["switch_type"] = self._switch.get('switch_type')
        
        # Include information about all entities if available
        if 'entities' in self._switch:
            attributes["entities_count"] = len(self._switch['entities'])
            attributes["all_entities"] = self._switch['entities']
            
        return attributes

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information to link entities to device registry."""
        device_info = {
            "identifiers": {(DOMAIN, self._switch["deviceSerial"])},
            "name": self._switch["name"],
            "manufacturer": "EZVIZ",
            "model": self._switch.get("deviceType", "Unknown"),
        }
        
        # Add software version if available
        if "version" in self._switch:
            device_info["sw_version"] = self._switch["version"]
            
        return device_info

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        # Determine icon based on the switch type or device type
        switch_type = self._switch.get('switch_type', DeviceSwitchType.PLUG.value)
        
        # Use proper mapping based on DeviceSwitchType values
        if switch_type == DeviceSwitchType.DOORBELL_TALK.value:  # DOORBELL_TALK (101)
            return "mdi:doorbell"
        elif switch_type == DeviceSwitchType.ALARM_TONE.value:  # ALARM_TONE (1)
            return "mdi:bell-ring"
        elif switch_type == DeviceSwitchType.LIGHT.value:  # LIGHT (3)
            return "mdi:lightbulb"
        elif switch_type == DeviceSwitchType.OUTDOOR_RINGING_SOUND.value:  # OUTDOOR_RINGING_SOUND (39)
            return "mdi:volume-high"
        elif switch_type == DeviceSwitchType.ALARM_LIGHT.value:  # ALARM_LIGHT (303)
            return "mdi:alarm-light"
        elif switch_type == DeviceSwitchType.INFRARED_LIGHT.value:  # INFRARED_LIGHT (10)
            return "mdi:flashlight"
        elif switch_type == DeviceSwitchType.PLUG.value:  # PLUG (14)
            # Use regional specific icons for plugs based on device type/serial
            if self._switch["deviceType"].endswith("EU"):
                return "mdi:power-socket-de"
            elif self._switch["deviceSerial"].endswith("US"):
                return "mdi:power-socket-us"
            else:
                return "mdi:power-socket"
        # Default for any other switchable device
        else:
            return "mdi:toggle-switch"
