from datetime import timedelta
import logging
from typing import Any, Callable, Dict, Optional, TypedDict

import async_timeout
from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
import voluptuous as vol

from .const import DOMAIN
from .protocol import get_print_job_status

LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required('ip'): cv.string,
        vol.Required('port'): cv.string,
    }
)

class PrinterDefinition(TypedDict):
    ip: str
    port: int


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: Callable,
) -> bool:
    config = hass.data[DOMAIN][config_entry.entry_id]
    if config_entry.options:
        config.update(config_entry.options)
    coordinator = FlashforgeAdventurer3Coordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()
    sensors = [
        FlashforgeAdventurer3StateSensor(coordinator, config),
        FlashforgeAdventurer3ProgressSensor(coordinator, config),
        FlashforgeAdventurer3NozzleTemperatureSensor(coordinator, config),
        FlashforgeAdventurer3BedTemperatureSensor(coordinator, config),
        FlashforgeAdventurer3MachineStatusSensor(coordinator, config),
        FlashforgeAdventurer3MoveModeSensor(coordinator, config),
        FlashforgeAdventurer3CurrentFileSensor(coordinator, config),
    ]
    async_add_entities(sensors, update_before_add=True)


class FlashforgeAdventurer3Coordinator(DataUpdateCoordinator):
    def __init__(self, hass, printer_definition: PrinterDefinition):
        super().__init__(
            hass,
            LOGGER,
            name='My sensor',
            update_interval=timedelta(seconds=20),
        )
        self.ip = printer_definition['ip_address']
        self.port = printer_definition['port']

    async def _async_update_data(self):
        async with async_timeout.timeout(5):
            return await get_print_job_status(self.ip, self.port)


class FlashforgeAdventurer3CommonPropertiesMixin:
    @property
    def name(self) -> str:
        return f'FlashForge Adventurer 3'

    @property
    def unique_id(self) -> str:
        return f'flashforge_adventurer_3_{self.ip}'


class BaseFlashforgeAdventurer3Sensor(FlashforgeAdventurer3CommonPropertiesMixin, CoordinatorEntity, Entity):
    def __init__(self, coordinator: DataUpdateCoordinator, printer_definition: PrinterDefinition) -> None:
        super().__init__(coordinator)
        self.ip = printer_definition['ip_address']
        self.port = printer_definition['port']
        self._available = False
        self.attrs = {}

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        return self.attrs

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return self.attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        self.attrs = self.coordinator.data
        self.async_write_ha_state()


class FlashforgeAdventurer3StateSensor(BaseFlashforgeAdventurer3Sensor):
    @property
    def name(self) -> str:
        return f'{super().name} state'

    @property
    def unique_id(self) -> str:
        return f'{super().unique_id}_state'

    @property
    def available(self) -> bool:
        return True

    @property
    def state(self) -> Optional[str]:
        if self.attrs.get('online'):
            if self.attrs.get('printing'):
                return 'printing'
            else:
                return 'online'
        else:
            return 'offline'

    @property
    def icon(self) -> str:
        return 'mdi:printer-3d'


class FlashforgeAdventurer3ProgressSensor(BaseFlashforgeAdventurer3Sensor):
    @property
    def name(self) -> str:
        return f'{super().name} progress'

    @property
    def unique_id(self) -> str:
        return f'{super().unique_id}_progress'

    @property
    def available(self) -> bool:
        return bool(self.attrs.get('online'))

    @property
    def state(self) -> Optional[str]:
        return self.attrs.get('progress', 0)

    @property
    def icon(self) -> str:
        return 'mdi:percent-circle'

    @property
    def unit_of_measurement(self) -> str:
        return '%'

class FlashforgeAdventurer3NozzleTemperatureSensor(BaseFlashforgeAdventurer3Sensor):
    @property
    def name(self) -> str:
        return f'{super().name} nozzle temperature'

    @property
    def unique_id(self) -> str:
        return f'{super().unique_id}_nozzle_temperature'

    @property
    def available(self) -> bool:
        return bool(self.attrs.get('online'))

    @property
    def state(self) -> Optional[str]:
        return self.attrs.get('nozzle_temperature', 0)

    @property
    def icon(self) -> str:
        return 'mdi:printer-3d-nozzle-heat'

    @property
    def unit_of_measurement(self) -> str:
        return '°C'

class FlashforgeAdventurer3BedTemperatureSensor(BaseFlashforgeAdventurer3Sensor):
    @property
    def name(self) -> str:
        return f'{super().name} bed temperature'

    @property
    def unique_id(self) -> str:
        return f'{super().unique_id}_bed_temperature'

    @property
    def available(self) -> bool:
        return bool(self.attrs.get('online'))

    @property
    def state(self) -> Optional[str]:
        return self.attrs.get('bed_temperature', 0)

    @property
    def icon(self) -> str:
        return 'mdi:heating-coil'

    @property
    def unit_of_measurement(self) -> str:
        return '°C'

class FlashforgeAdventurer3MachineStatusSensor(BaseFlashforgeAdventurer3Sensor):
    @property
    def name(self) -> str:
        return f'{super().name} machine status'

    @property
    def unique_id(self) -> str:
        return f'{super().unique_id}_machine_status'

    @property
    def available(self) -> bool:
        return bool(self.attrs.get('online'))

    @property
    def state(self) -> Optional[str]:
        return self.attrs.get('machine_status', 0)

    @property
    def icon(self) -> str:
        return 'mdi:printer-3d'

class FlashforgeAdventurer3MoveModeSensor(BaseFlashforgeAdventurer3Sensor):
    @property
    def name(self) -> str:
        return f'{super().name} move mode'

    @property
    def unique_id(self) -> str:
        return f'{super().unique_id}_move_mode'

    @property
    def available(self) -> bool:
        return bool(self.attrs.get('online'))

    @property
    def state(self) -> Optional[str]:
        return self.attrs.get('move_mode', 0)

    @property
    def icon(self) -> str:
        return 'mdi:printer-3d-nozzle'

class FlashforgeAdventurer3CurrentFileSensor(BaseFlashforgeAdventurer3Sensor):
    @property
    def name(self) -> str:
        return f'{super().name} current file'

    @property
    def unique_id(self) -> str:
        return f'{super().unique_id}_current_file'

    @property
    def available(self) -> bool:
        return bool(self.attrs.get('online'))

    @property
    def state(self) -> Optional[str]:
        return self.attrs.get('current_file', 0)

    @property
    def icon(self) -> str:
        return 'mdi:file'




"""
response['printing'] = bool(desired_nozzle_temperature and desired_bed_temperature)
        response['nozzle_temperature'] = float(temperature_match.group(1))
        response['desired_nozzle_temperature'] = desired_nozzle_temperature
        response['bed_temperature'] = float(temperature_match.group(3))
        response['desired_bed_temperature'] = desired_bed_temperature
    status_match = STATUS_REGEX.match(status_info)
    if status_match:
        response['MachineStatus'] = status_match.group(1)
        response['MoveMode'] = status_match.group(2)
        """
