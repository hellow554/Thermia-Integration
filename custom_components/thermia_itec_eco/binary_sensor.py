"""Binary sensors: running states, flags and switches observed on the bus."""
from __future__ import annotations

import time

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import ThermiaBaseEntity
from .const import DOMAIN
from .fields import FIELDS, FieldDef, device_of
from .runtime import ThermiaRuntime


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: ThermiaRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FieldBinarySensor(runtime, entry, fdef)
            for fdef in FIELDS
            if fdef.kind == "binary" and not fdef.blocked
        ]
    )


class FieldBinarySensor(ThermiaBaseEntity, BinarySensorEntity):
    def __init__(self, runtime: ThermiaRuntime, entry: ConfigEntry, fdef: FieldDef) -> None:
        super().__init__(runtime, entry, fdef.key, device=device_of(fdef), diagnostic=fdef.diagnostic,
                         enabled_default=fdef.enabled_default)
        self._fdef = fdef
        self._attr_device_class = (
            BinarySensorDeviceClass(fdef.device_class) if fdef.device_class else None
        )

    def _refresh(self) -> None:
        self._attr_is_on = self._fdef.getter(self._runtime.decoder, time.monotonic())
