"""Text sensor platform: enum and derived text values, plus text diagnostics."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor

from . import ThermiaBus  # noqa: F401
from .catalogue import DIAG_SENSORS, FIELDS

CONF_KEY = "key"
CONF_THERMIA_BUS_ID = "thermia_bus_id"

KEYS = [f.key for f in FIELDS if f.kind == "text"] + [k for k, kind, *_ in DIAG_SENSORS if kind == "text"]

CONFIG_SCHEMA = text_sensor.text_sensor_schema().extend(
    {
        cv.Required(CONF_THERMIA_BUS_ID): cv.use_id(ThermiaBus),
        cv.Required(CONF_KEY): cv.one_of(*KEYS, lower=False),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_THERMIA_BUS_ID])
    var = await text_sensor.new_text_sensor(config)
    cg.add(parent.register_text_sensor(config[CONF_KEY], var))
