from __future__ import annotations

from homeassistant.const import Platform


DOMAIN = "modulating_thermostat"
PLATFORMS = [Platform.SENSOR]

CONF_ZONES = "zones"
CONF_ZONE_ID = "zone_id"
CONF_WEIGHT = "weight"
CONF_TEMPERATURE_ENTITY = "temperature_entity"
CONF_SETPOINT_ENTITY = "setpoint_entity"
CONF_ACTUATOR_ENTITY = "actuator_entity"
CONF_ACTUATOR_MIN = "actuator_min"
CONF_ACTUATOR_MAX = "actuator_max"
CONF_DEADBAND = "deadband"

CONF_OUTDOOR_ENTITY = "outdoor_entity"
CONF_FLOW_SENSOR_ENTITY = "flow_sensor_entity"
CONF_AGGRESSIVENESS_ENTITY = "aggressiveness_entity"
CONF_DEFAULT_AGGRESSIVENESS = "default_aggressiveness"
CONF_OUTPUT_MIN = "output_min"
CONF_OUTPUT_MAX = "output_max"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_NAME = "name"
CONF_ACTIVE_MIN_FLOW = "active_min_flow"

CONF_WEATHER_REF = "weather_reference_temperature"
CONF_WEATHER_SLOPE_ECO = "weather_slope_eco"
CONF_WEATHER_SLOPE_BOOST = "weather_slope_boost"
CONF_WEATHER_OFFSET = "weather_offset"

CONF_ZONE_NAME = "name"
CONF_CONTROLLERS = "controllers"
CONF_LOG_LEVEL = "log_level"

DEFAULT_DEADBAND = 0.1
DEFAULT_UPDATE_INTERVAL = 30
DEFAULT_OUTPUT_MIN = 25.0
DEFAULT_OUTPUT_MAX = 75.0
DEFAULT_ACTIVE_MIN_FLOW = 30.0
DEFAULT_DEFAULT_AGGRESSIVENESS = 50.0
DEFAULT_WEATHER_REF = 21.0
DEFAULT_WEATHER_SLOPE_ECO = 1.2
DEFAULT_WEATHER_SLOPE_BOOST = 2.0
DEFAULT_WEATHER_OFFSET = 20.0

STORAGE_VERSION = 1
