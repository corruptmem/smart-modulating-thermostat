from __future__ import annotations

from typing import Any, Mapping, cast

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service

from .const import (
    CONF_ACTIVE_MIN_FLOW,
    CONF_ACTUATOR_ENTITY,
    CONF_ACTUATOR_MAX,
    CONF_ACTUATOR_MIN,
    CONF_AGGRESSIVENESS_ENTITY,
    CONF_DEFAULT_AGGRESSIVENESS,
    CONF_DEADBAND,
    CONF_FLOW_SENSOR_ENTITY,
    CONF_NAME,
    CONF_OUTDOOR_ENTITY,
    CONF_OUTPUT_MAX,
    CONF_OUTPUT_MIN,
    CONF_SETPOINT_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_UPDATE_INTERVAL,
    CONF_WEIGHT,
    CONF_WEATHER_OFFSET,
    CONF_WEATHER_REF,
    CONF_WEATHER_SLOPE_BOOST,
    CONF_WEATHER_SLOPE_ECO,
    CONF_ZONES,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_CONTROLLERS,
    CONF_LOG_LEVEL,
    DEFAULT_ACTIVE_MIN_FLOW,
    DEFAULT_DEADBAND,
    DEFAULT_DEFAULT_AGGRESSIVENESS,
    DEFAULT_OUTPUT_MAX,
    DEFAULT_OUTPUT_MIN,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_WEATHER_OFFSET,
    DEFAULT_WEATHER_REF,
    DEFAULT_WEATHER_SLOPE_BOOST,
    DEFAULT_WEATHER_SLOPE_ECO,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import ModulatingThermostatCoordinator, merge_entry_data


def _extract_controllers(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        controllers_dict = cast(dict[str, Any], value)
        controllers_raw = controllers_dict.get(CONF_CONTROLLERS)
        if controllers_raw is None:
            raise vol.Invalid("missing 'controllers' key")
        return cast(list[dict[str, Any]], controllers_raw)
    return cast(list[dict[str, Any]], value)


ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE_ID): cv.slug,
        vol.Optional(CONF_ZONE_NAME): cv.string,
        vol.Optional(CONF_WEIGHT, default=1.0): vol.Coerce(float),
        vol.Required(CONF_TEMPERATURE_ENTITY): cv.entity_id,
        vol.Required(CONF_SETPOINT_ENTITY): cv.entity_id,
        vol.Optional(CONF_ACTUATOR_ENTITY): cv.entity_id,
        vol.Optional(CONF_ACTUATOR_MIN, default=0.0): vol.Coerce(float),
        vol.Optional(CONF_ACTUATOR_MAX, default=100.0): vol.Coerce(float),
        vol.Optional(CONF_DEADBAND, default=DEFAULT_DEADBAND): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=2.0)
        ),
    }
)

CONTROLLER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_OUTDOOR_ENTITY): cv.entity_id,
        vol.Optional(CONF_FLOW_SENSOR_ENTITY): cv.entity_id,
        vol.Optional(CONF_AGGRESSIVENESS_ENTITY): cv.entity_id,
        vol.Optional(CONF_DEFAULT_AGGRESSIVENESS, default=DEFAULT_DEFAULT_AGGRESSIVENESS): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
        vol.Optional(CONF_OUTPUT_MIN, default=DEFAULT_OUTPUT_MIN): vol.Coerce(float),
        vol.Optional(CONF_OUTPUT_MAX, default=DEFAULT_OUTPUT_MAX): vol.Coerce(float),
        vol.Optional(CONF_ACTIVE_MIN_FLOW, default=DEFAULT_ACTIVE_MIN_FLOW): vol.Coerce(float),
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=600)
        ),
        vol.Optional(CONF_WEATHER_REF, default=DEFAULT_WEATHER_REF): vol.Coerce(float),
        vol.Optional(CONF_WEATHER_SLOPE_ECO, default=DEFAULT_WEATHER_SLOPE_ECO): vol.Coerce(float),
        vol.Optional(CONF_WEATHER_SLOPE_BOOST, default=DEFAULT_WEATHER_SLOPE_BOOST): vol.Coerce(float),
        vol.Optional(CONF_WEATHER_OFFSET, default=DEFAULT_WEATHER_OFFSET): vol.Coerce(float),
        vol.Optional(CONF_LOG_LEVEL): cv.string,
        vol.Required(CONF_ZONES): vol.All(cv.ensure_list, [ZONE_SCHEMA]),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(_extract_controllers, cv.ensure_list, [CONTROLLER_SCHEMA])}, extra=vol.ALLOW_EXTRA
)

async def async_setup(hass: HomeAssistant, config: Mapping[str, Any]) -> bool:
    hass.data.setdefault(DOMAIN, {})
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    yaml_config = config.get(DOMAIN)
    if yaml_config:
        for controller_data in yaml_config:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data=controller_data,
                )
            )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = merge_entry_data(entry)
    coordinator = ModulatingThermostatCoordinator(hass, entry.entry_id, data)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await coordinator.async_load_runtime()
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ModulatingThermostatCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_unload()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
