"""Climate platform: the room thermostat (10..30 degC, heat)."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import climate
from esphome.const import CONF_ID

from . import ThermiaBus, thermia_ns

ThermiaClimate = thermia_ns.class_("ThermiaClimate", climate.Climate, cg.Component)

CONF_THERMIA_BUS_ID = "thermia_bus_id"

CONFIG_SCHEMA = climate.climate_schema(ThermiaClimate).extend(
    {cv.Required(CONF_THERMIA_BUS_ID): cv.use_id(ThermiaBus)}
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await climate.register_climate(var, config)
    parent = await cg.get_variable(config[CONF_THERMIA_BUS_ID])
    cg.add(var.set_parent(parent))
    cg.add(parent.register_climate(var))
