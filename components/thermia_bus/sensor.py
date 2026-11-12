"""Sensor platform: numeric register fields and numeric diagnostics."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor

from . import ThermiaBus, thermia_ns  # noqa: F401
from .catalogue import DIAG_SENSORS, FIELDS

CONF_KEY = "key"
CONF_THERMIA_BUS_ID = "thermia_bus_id"

KEYS = [f.key for f in FIELDS if f.kind == "sensor"] + [k for k, kind, *_ in DIAG_SENSORS if kind == "sensor"]

CONFIG_SCHEMA = sensor.sensor_schema().extend(
    {
        cv.Required(CONF_THERMIA_BUS_ID): cv.use_id(ThermiaBus),
        cv.Required(CONF_KEY): cv.one_of(*KEYS, lower=False),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_THERMIA_BUS_ID])
    var = await sensor.new_sensor(config)
    cg.add(parent.register_sensor(config[CONF_KEY], var))
