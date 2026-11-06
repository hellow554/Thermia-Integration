"""Thermia iTec Eco integration: passive monitoring plus optional room sensor and 0x0F emulation."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .base import device_info
from .const import CONF_PORT, DOMAIN
from .runtime import ThermiaRuntime

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.BUTTON,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    options = {**entry.data, **entry.options}
    runtime = ThermiaRuntime(hass, entry.entry_id, entry.data[CONF_PORT], options)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    # Create the parent device first so the DCM and room devices can link to it.
    dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, **{
        k: v for k, v in device_info(entry, "heat_pump").items() if k != "via_device"
    })
    await runtime.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    runtime: ThermiaRuntime = hass.data[DOMAIN].pop(entry.entry_id)
    await runtime.async_stop()
    return unload_ok


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
