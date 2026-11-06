"""Switch for the 0x0F ACK emulation."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import ThermiaBaseEntity
from .const import DOMAIN
from .runtime import ThermiaRuntime


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: ThermiaRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AckEmulationSwitch(runtime, entry)])


class AckEmulationSwitch(ThermiaBaseEntity, SwitchEntity):
    def __init__(self, runtime: ThermiaRuntime, entry: ConfigEntry) -> None:
        super().__init__(runtime, entry, "ack_emulation_0f", device="dcm")

    def _refresh(self) -> None:
        self._attr_is_on = self._runtime.ack.enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self._runtime.async_set_ack_emulation(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._runtime.async_set_ack_emulation(False)
