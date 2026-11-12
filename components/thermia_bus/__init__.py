"""ESPHome component for the Thermia iTec Eco bus (Waveshare ESP32-S3-Relay-1CH).

Protocol logic is in thermia_core (C++). This Python part only validates YAML and wires the objects.
"""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import pins
from esphome.components import uart
from esphome.const import CONF_ID

DEPENDENCIES = ["uart"]
AUTO_LOAD = []
CODEOWNERS = []

thermia_ns = cg.esphome_ns.namespace("thermia_bus")
ThermiaBus = thermia_ns.class_("ThermiaBus", cg.Component, uart.UARTDevice)

CONF_DE_PIN = "de_pin"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(ThermiaBus),
        cv.Required(CONF_DE_PIN): pins.gpio_output_pin_schema,
    }
).extend(cv.COMPONENT_SCHEMA).extend(uart.UART_DEVICE_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)
    de = await cg.gpio_pin_expression(config[CONF_DE_PIN])
    cg.add(var.set_de_pin(de))
