"""Shared base class for Thermia entities: dispatcher updates and device grouping.

Three devices, all under the heat pump integration:
- heat_pump: the iTec Eco itself (sensors, binary sensors, bus diagnostics)
- dcm:       Online/DCM module (0x0F ACK switch and its status)
- room:      room thermostat (climate, room sensor switch, hot-water button, status)
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityCategory

from .const import DOMAIN

DEVICE_NAMES = {
    "heat_pump": "Thermia iTec Eco",
    "controller": "Regler (0x02)",
    "accessory": "Zubehör-Schnittstelle (0x06)",
    "room": "Raumregler (0x0A)",
    "dcm": "DCM / Online-Modul (0x0F)",
    "outdoor": "Außeneinheit (0x1E)",
}


def device_info(entry: ConfigEntry, device: str) -> DeviceInfo:
    if device == "heat_pump":
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEVICE_NAMES["heat_pump"],
            manufacturer="Thermia",
            model="iTec Eco 5 kW",
        )
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{device}")},
        name=DEVICE_NAMES[device],
        manufacturer="Thermia",
        model=DEVICE_NAMES[device],
        via_device=(DOMAIN, entry.entry_id),
    )


class ThermiaBaseEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime, entry: ConfigEntry, key: str, *,
                 device: str = "heat_pump", diagnostic: bool = False,
                 enabled_default: bool = True) -> None:
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info(entry, device)
        self._attr_entity_registry_enabled_default = enabled_default
        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._runtime.signal, self._handle_update)
        )
        self._refresh()

    @callback
    def _handle_update(self) -> None:
        self._refresh()
        self.async_write_ha_state()

    def _refresh(self) -> None:
        raise NotImplementedError
