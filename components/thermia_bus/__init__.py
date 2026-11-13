"""ESPHome component for the Thermia iTec Eco bus (Waveshare ESP32-S3-Relay-1CH).

Protocol logic is in thermia_core (C++). This Python part only validates YAML and wires the objects.
"""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import pins
from esphome.components import sensor as esphome_sensor, uart
from esphome.const import CONF_ID

DEPENDENCIES = ["uart"]
AUTO_LOAD = []
CODEOWNERS = []

thermia_ns = cg.esphome_ns.namespace("thermia_bus")
ThermiaBus = thermia_ns.class_("ThermiaBus", cg.Component, uart.UARTDevice)

CONF_DE_PIN = "de_pin"
CONF_DCM = "dcm"
CONF_0X0F_EMULATION = "0x0f_emulation"
CONF_ROOM_TEMPERATURE = "room_temperature"
CONF_ROOM_TEMPERATURE_SENSOR = "room_temperature_sensor"
CONF_ENABLE = "enable"
CONF_REGISTER_STALE_AFTER = "register_stale_after"

DCM_SCHEMA = cv.Schema(
    {
        cv.Optional(CONF_0X0F_EMULATION, default=False): cv.boolean,
    }
)

ROOM_TEMPERATURE_SCHEMA = cv.Schema(
    {
        cv.Optional(CONF_ENABLE): cv.boolean,
        cv.Optional(CONF_ROOM_TEMPERATURE_SENSOR): cv.use_id(esphome_sensor.Sensor),
    }
)


def validate_room_temperature(config):
    room_config = config[CONF_ROOM_TEMPERATURE]
    has_sensor = CONF_ROOM_TEMPERATURE_SENSOR in room_config
    enabled = room_config.get(CONF_ENABLE, has_sensor)
    if enabled and not has_sensor:
        raise cv.Invalid(
            "room_temperature.enable is true, but room_temperature.room_temperature_sensor is missing"
        )
    # Store the resolved value so code generation and diagnostics have one unambiguous setting.
    room_config[CONF_ENABLE] = enabled
    return config


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(ThermiaBus),
            cv.Required(CONF_DE_PIN): pins.gpio_output_pin_schema,
            cv.Optional(CONF_DCM, default={}): DCM_SCHEMA,
            cv.Optional(CONF_ROOM_TEMPERATURE, default={}): ROOM_TEMPERATURE_SCHEMA,
            # 0 disables expiry. A positive value invalidates register values after N seconds.
            cv.Optional(CONF_REGISTER_STALE_AFTER, default=0): cv.int_range(min=0, max=86400),
        }
    ).extend(cv.COMPONENT_SCHEMA).extend(uart.UART_DEVICE_SCHEMA),
    validate_room_temperature,
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)
    de = await cg.gpio_pin_expression(config[CONF_DE_PIN])
    cg.add(var.set_de_pin(de))

    dcm_config = config[CONF_DCM]
    cg.add(var.set_ack_emulation_enabled(dcm_config[CONF_0X0F_EMULATION]))

    room_config = config[CONF_ROOM_TEMPERATURE]
    cg.add(var.set_room_emulation_enabled(room_config[CONF_ENABLE]))
    sensor_id = room_config.get(CONF_ROOM_TEMPERATURE_SENSOR)
    if sensor_id is not None:
        room_sensor = await cg.get_variable(sensor_id)
        cg.add(var.set_room_temperature_sensor(room_sensor))

    cg.add(var.set_register_stale_after_seconds(config[CONF_REGISTER_STALE_AFTER]))
