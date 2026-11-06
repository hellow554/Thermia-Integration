"""Button: one-shot hot-water top-up, sent in the next room sensor response."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import ThermiaBaseEntity
from .const import DOMAIN
from .runtime import ThermiaRuntime


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: ThermiaRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ThermiaTopupButton(runtime, entry)])


class ThermiaTopupButton(ThermiaBaseEntity, ButtonEntity):
    def __init__(self, runtime: ThermiaRuntime, entry: ConfigEntry) -> None:
        super().__init__(runtime, entry, "dhw_topup", device="room")

    def _refresh(self) -> None:
        return None

    async def async_press(self) -> None:
        await self._runtime.async_request_topup()
