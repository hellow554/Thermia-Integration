"""Room thermostat: forwards the room temperature to the heat pump and sets the room setpoint."""
from __future__ import annotations

import time

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import ThermiaBaseEntity
from .const import DOMAIN
from .emulation import SETPOINT_MAX, SETPOINT_MIN
from .fields import FIELDS
from .runtime import ThermiaRuntime

_HEATING_ACTIVE = next(f for f in FIELDS if f.key == "heating_active")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: ThermiaRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ThermiaRoomThermostat(runtime, entry)])


class ThermiaRoomThermostat(ThermiaBaseEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_min_temp = float(SETPOINT_MIN)
    _attr_max_temp = float(SETPOINT_MAX)
    _attr_target_temperature_step = 1.0

    def __init__(self, runtime: ThermiaRuntime, entry: ConfigEntry) -> None:
        super().__init__(runtime, entry, "room_thermostat", device="room")

    def _refresh(self) -> None:
        room = self._runtime.room
        self._attr_current_temperature = room.temperature
        self._attr_target_temperature = float(room.target)
        heating = _HEATING_ACTIVE.getter(self._runtime.decoder, time.monotonic())
        self._attr_hvac_action = HVACAction.HEATING if heating else HVACAction.IDLE

    async def async_set_temperature(self, **kwargs) -> None:
        value = kwargs.get(ATTR_TEMPERATURE)
        if value is None:
            return
        await self._runtime.async_set_target(value)
