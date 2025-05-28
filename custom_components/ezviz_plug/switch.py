"""Support for EzvizSwitch."""
from __future__ import annotations

import logging
from typing import Any, Dict
from datetime import datetime, timedelta
import voluptuous as vol
import requests

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

from .http_client import EzvizHttpClient
from .const import DOMAIN
from .coordinator import EzvizDataUpdateCoordinator

# Define switch types that match those in pyezviz.constants.DeviceSwitchType
class DeviceSwitchType:
    """Device switch types."""
    ALARM_TONE = 1
    LIGHT = 3
    INFRARED_LIGHT = 10
    PLUG = 14
    OUTDOOR_RINGING_SOUND = 39
    DOORBELL_TALK = 101
    ALARM_LIGHT = 303

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
    """Perform the setup for Ezviz switchable devices.
    
    Creates individual entities for each switchable feature of a device, allowing
    separate control of different functions (lights, alarms, etc.) on the same
    physical device.
    """

    _LOGGER.debug('calling setup_platform')

    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    ezvizClient = EzvizHttpClient(email, password)

    try:
        auth_data = await hass.async_add_executor_job(ezvizClient.login)
    except requests.exceptions.ConnectionError:
        _LOGGER.exception('Cannot connect to API')
    except Exception as error:
        if "verification code" in str(error).lower():
            _LOGGER.exception('MFA Required')
        else:
            _LOGGER.exception('Unexpected exception: %s', error)

    coordinator = EzvizDataUpdateCoordinator(hass, api=ezvizClient, api_timeout=10)

    # Add devices
    entities = []
    devices = await coordinator._async_update_data();
    
    for key, device in devices.items():
        # Check if device has multiple entities
        if 'entities' in device and len(device['entities']) > 1:
            # Create an entity for each switchable feature
            for i, entity_data in enumerate(device['entities']):
                entities.append(Ezvizswitch(device, ezvizClient, entity_data=entity_data, entity_index=i))
                _LOGGER.debug("Created entity for device %s: %s (type: %s)", 
                            device['deviceSerial'], entity_data.get('switch_type', 'unknown'))
        else:
            # Create a single entity for backward compatibility
            entities.append(Ezvizswitch(device, ezvizClient))
            _LOGGER.debug("Created single entity for device %s", device['deviceSerial'])

    add_entities(entities)

    # Do not close the client session as it's needed by the entities
    # _LOGGER.info('Closing the Client session.')
    # ezvizClient.close_session()


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    """Set up Ezviz switch based on a config entry.
    
    Creates individual entities for each switchable feature of a device, allowing
    separate control of different functions (lights, alarms, etc.) on the same
    physical device.
    """

    email = hass.data[DOMAIN][entry.entry_id][CONF_EMAIL]
    password = hass.data[DOMAIN][entry.entry_id][CONF_PASSWORD]
    ezvizClient = EzvizHttpClient(email, password)

    try:
        auth_data = await hass.async_add_executor_job(ezvizClient.login)
    except requests.exceptions.ConnectionError:
        _LOGGER.exception('Cannot connect to API')
    except Exception as error:
        if "verification code" in str(error).lower():
            _LOGGER.exception('MFA Required')
        else:
            _LOGGER.exception('Unexpected exception: %s', error)

    coordinator = EzvizDataUpdateCoordinator(hass, api=ezvizClient, api_timeout=10)

    # Add devices
    entities = []
    devices = await coordinator._async_update_data();
    
    for key, device in devices.items():
        # Check if device has multiple entities
        if 'entities' in device and len(device['entities']) > 1:
            # Create an entity for each switchable feature
            for i, entity_data in enumerate(device['entities']):
                entities.append(Ezvizswitch(device, ezvizClient, entity_data=entity_data, entity_index=i))
                _LOGGER.debug("Created entity for device %s: %s (type: %s)", 
                            device['deviceSerial'], entity_data.get('switch_type', 'unknown'))
        else:
            # Create a single entity for backward compatibility
            entities.append(Ezvizswitch(device, ezvizClient))
            _LOGGER.debug("Created single entity for device %s", device['deviceSerial'])

    async_add_entities(entities)

    # Do not close the client session as it's needed by the entities
    # _LOGGER.debug('Closing the Client session.')
    # ezvizClient.close_session()


class Ezvizswitch(SwitchEntity, RestoreEntity):
    """Representation of Ezviz Switchable Device Entity.
    
    This class handles all types of EZVIZ devices that have switchable features,
    including smart plugs, doorbells, security cameras, and other devices with
    switchable components like lights, alarms, etc.
    
    Each device can have multiple switchable entities, with each entity representing
    a specific switchable feature (e.g., light, alarm, doorbell, etc.).
    """

    def __init__(self, switch, ezvizClient, entity_data=None, entity_index=None) -> None:
        """Initialize the Ezviz device.
        
        Args:
            switch: The device data containing information about the device
            ezvizClient: The Ezviz client for API communication
            entity_data: Specific entity data if this is a sub-entity of a device
            entity_index: Index of this entity in the device's entities list
        """
        self._state = None
        self._last_run_success = None
        self._last_pressed: datetime | None = None
        self._switch = switch
        self._ezviz_client = ezvizClient
        self._entity_data = entity_data
        self._entity_index = entity_index
        
        # For entities with specific entity_data, use its switch_type
        if entity_data:
            self._switch_type = entity_data['switch_type']
            self._enable = entity_data['enable']
        else:
            # For backward compatibility - use the device's primary switch type
            self._switch_type = switch.get('switch_type', DeviceSwitchType.PLUG.value)
            self._enable = switch.get('enable', False)

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

        _LOGGER.debug('Turning on %s (current state is: %s)', self.name, self._state)

        # Use the entity-specific switch type
        if self._ezviz_client.switch_status(self._switch["deviceSerial"], self._switch_type, 1):
            self._state = True
            self._enable = True
            if self._entity_data:
                self._entity_data['enable'] = True
            else:
                self._switch['enable'] = True
            self._last_pressed = dt_util.utcnow()
            self._last_run_success = True
        else:
            self._last_run_success = False

    def turn_off(self, **kwargs) -> None:
        """Turn device off."""
        _LOGGER.debug('Turning off %s (current state is: %s)', self.name, self._state)

        # Use the entity-specific switch type
        if self._ezviz_client.switch_status(self._switch["deviceSerial"], self._switch_type, 0):
            self._state = False
            self._enable = False
            if self._entity_data:
                self._entity_data['enable'] = False
            else:
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
        _LOGGER.debug("calling update method for %s", self.name)

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
                    
                    # Update our device data
                    self._switch = device
                    
                    # If this is an entity-specific instance, update the entity data
                    if self._entity_data and self._entity_index is not None and 'entities' in device:
                        if 0 <= self._entity_index < len(device['entities']):
                            # Update the entity data with the latest from the API
                            self._entity_data = device['entities'][self._entity_index]
                            self._switch_type = self._entity_data['switch_type']
                            self._enable = self._entity_data['enable']
                    
                    break
        except Exception as ex:
            _LOGGER.error("Error updating entity %s: %s", self.name, ex)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""

        if not isinstance(self._state, bool):
            self._state = (True if self._enable == 1 or self._enable is True else False)

        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return False if self._switch['status'] == 2 else True

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        if self._entity_data:
            # For entity-specific switches, include the switch type in the ID
            return f"{self._switch['deviceSerial']}_{self._switch_type}"
        else:
            # For backward compatibility
            return self._switch['deviceSerial']

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        # If this is a specific entity from a device with multiple entities, append the entity type
        if self._entity_data and 'entities' in self._switch and len(self._switch['entities']) > 1:
            # Get a friendly name for the switch type
            switch_type_name = self._get_switch_type_name(self._switch_type)
            return f"{self._switch['name']} {switch_type_name}"
        else:
            return self._switch['name']
            
    def _get_switch_type_name(self, switch_type):
        """Get a friendly name for the switch type."""
        # Map switch types to user-friendly names
        switch_type_names = {
            DeviceSwitchType.ALARM_TONE.value: "Alarm",
            DeviceSwitchType.LIGHT.value: "Light", 
            DeviceSwitchType.PLUG.value: "Plug",
            DeviceSwitchType.DOORBELL_TALK.value: "Doorbell",
            DeviceSwitchType.OUTDOOR_RINGING_SOUND.value: "Ringing Sound",
            DeviceSwitchType.ALARM_LIGHT.value: "Alarm Light",
            DeviceSwitchType.INFRARED_LIGHT.value: "IR Light"
        }
        return switch_type_names.get(switch_type, f"Switch {switch_type}")

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
        
        # Always include the switch type in the attributes
        attributes["switch_type"] = self._switch_type
        
        # For the main device entity, include information about all entities
        if not self._entity_data and 'entities' in self._switch:
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
        # Determine icon based on the entity's switch type
        switch_type = self._switch_type
        
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
