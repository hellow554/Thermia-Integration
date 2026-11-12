"""Binary sensor platform: running states, flags and switches seen on the bus."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor

from . import ThermiaBus  # noqa: F401
from .catalogue import FIELDS

CONF_KEY = "key"
CONF_THERMIA_BUS_ID = "thermia_bus_id"

KEYS = [f.key for f in FIELDS if f.kind == "binary"]

CONFIG_SCHEMA = binary_sensor.binary_sensor_schema().extend(
    {
        cv.Required(CONF_THERMIA_BUS_ID): cv.use_id(ThermiaBus),
        cv.Required(CONF_KEY): cv.one_of(*KEYS, lower=False),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_THERMIA_BUS_ID])
    var = await binary_sensor.new_binary_sensor(config)
    cg.add(parent.register_binary_sensor(config[CONF_KEY], var))
