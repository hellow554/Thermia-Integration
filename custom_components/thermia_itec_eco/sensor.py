"""Sensors: numeric and text process values, emulation status and bus diagnostics."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
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
    entities: list[SensorEntity] = [
        FieldSensor(runtime, entry, fdef)
        for fdef in FIELDS
        if fdef.kind in ("sensor", "text") and not fdef.blocked
    ]
    entities += [
        ValueSensor(runtime, entry, "bus_status", lambda r: r.status,
                    diagnostic=True, enabled_default=False),
        ValueSensor(runtime, entry, "frames_ok", lambda r: r.parser.frames_ok,
                    state_class=SensorStateClass.TOTAL_INCREASING, diagnostic=True, enabled_default=False),
        ValueSensor(runtime, entry, "resync_bytes", lambda r: r.parser.resync_bytes,
                    state_class=SensorStateClass.TOTAL_INCREASING, diagnostic=True, enabled_default=False),
        ValueSensor(runtime, entry, "unmatched_responses", lambda r: r.decoder.unmatched_responses,
                    state_class=SensorStateClass.TOTAL_INCREASING, diagnostic=True, enabled_default=False),
        ValueSensor(runtime, entry, "room_emulation_status", lambda r: r.room_status_text(),
                    device="room", diagnostic=True, enabled_default=False),
        ValueSensor(runtime, entry, "room_responses_sent", lambda r: r.room.responses_sent,
                    state_class=SensorStateClass.TOTAL_INCREASING, device="room",
                    diagnostic=True, enabled_default=False),
        ValueSensor(runtime, entry, "ack_emulation_status", lambda r: r.ack_status_text(),
                    device="dcm", diagnostic=True, enabled_default=False),
        ValueSensor(runtime, entry, "ack_frames_sent",
                    lambda r: r.ack.acks_sent + r.ack.idle_replies_sent,
                    state_class=SensorStateClass.TOTAL_INCREASING, device="dcm",
                    diagnostic=True, enabled_default=False),
    ]
    async_add_entities(entities)


class FieldSensor(ThermiaBaseEntity, SensorEntity):
    def __init__(self, runtime: ThermiaRuntime, entry: ConfigEntry, fdef: FieldDef) -> None:
        super().__init__(runtime, entry, fdef.key, device=device_of(fdef), diagnostic=fdef.diagnostic,
                         enabled_default=fdef.enabled_default)
        self._fdef = fdef
        self._attr_native_unit_of_measurement = fdef.unit
        self._attr_device_class = SensorDeviceClass(fdef.device_class) if fdef.device_class else None
        self._attr_state_class = SensorStateClass(fdef.state_class) if fdef.state_class else None

    def _refresh(self) -> None:
        self._attr_native_value = self._fdef.getter(self._runtime.decoder, time.monotonic())


class ValueSensor(ThermiaBaseEntity, SensorEntity):
    def __init__(self, runtime: ThermiaRuntime, entry: ConfigEntry, key: str,
                 getter: Callable[[ThermiaRuntime], Any], *,
                 state_class: SensorStateClass | None = None, device: str = "heat_pump",
                 diagnostic: bool = False, enabled_default: bool = True) -> None:
        super().__init__(runtime, entry, key, device=device, diagnostic=diagnostic,
                         enabled_default=enabled_default)
        self._getter = getter
        self._attr_state_class = state_class

    def _refresh(self) -> None:
        self._attr_native_value = self._getter(self._runtime)
