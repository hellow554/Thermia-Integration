"""Config flow (serial port) and options flow (room sensor, watchdog, transmit release)."""
from __future__ import annotations

import os
from typing import Any

import serial
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_PORT,
    CONF_ROOM_SENSOR,
    CONF_WATCHDOG_MINUTES,
    DEFAULT_WATCHDOG_MINUTES,
    DOMAIN,
)
from .transport import open_serial

BY_ID_DIR = "/dev/serial/by-id"


def _list_ports() -> list[selector.SelectOptionDict]:
    """Preferred by-id links first, then any other detected serial device."""
    options: dict[str, str] = {}
    if os.path.isdir(BY_ID_DIR):
        for name in sorted(os.listdir(BY_ID_DIR)):
            options[os.path.join(BY_ID_DIR, name)] = name
    for info in serial.tools.list_ports.comports():
        options.setdefault(info.device, info.description or info.device)
    return [selector.SelectOptionDict(value=k, label=v) for k, v in options.items()]


def _probe(port: str) -> bool:
    """Open and close the port once to verify it is usable. Sends nothing."""
    try:
        open_serial(port, timeout=0.1).close()
    except (serial.SerialException, OSError):
        return False
    return True


class ThermiaItecEcoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> ThermiaOptionsFlow:
        return ThermiaOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        options = await self.hass.async_add_executor_job(_list_ports)

        if user_input is not None:
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(os.path.realpath(port))
            self._abort_if_unique_id_configured()
            if await self.hass.async_add_executor_job(_probe, port):
                # The room sensor is optional. It goes into options, so the options flow can clear it later.
                options = {}
                if user_input.get(CONF_ROOM_SENSOR):
                    options[CONF_ROOM_SENSOR] = user_input[CONF_ROOM_SENSOR]
                return self.async_create_entry(
                    title=f"Thermia iTec Eco ({port})",
                    data={CONF_PORT: port},
                    options=options,
                )
            errors["base"] = "cannot_open"

        if not options:
            return self.async_abort(reason="no_ports")

        schema = vol.Schema(
            {
                vol.Required(CONF_PORT, default=options[0]["value"]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_ROOM_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class ThermiaOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ROOM_SENSOR,
                    description={"suggested_value": current.get(CONF_ROOM_SENSOR)},
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                vol.Required(
                    CONF_WATCHDOG_MINUTES,
                    default=current.get(CONF_WATCHDOG_MINUTES, DEFAULT_WATCHDOG_MINUTES),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=120, step=5,
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="min",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
