from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_ACTIVE_MIN_FLOW,
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
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONES,
    CONF_ACTUATOR_ENTITY,
    CONF_ACTUATOR_MIN,
    CONF_ACTUATOR_MAX,
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
)


ENTITY_SELECTOR: Any = selector.EntitySelector(selector.EntitySelectorConfig())  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]


class ModulatingThermostatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the interactive setup flow and YAML imports."""
    VERSION = 1

    def __init__(self) -> None:
        self._config_data: dict[str, Any] = {}
        self._zones: list[dict[str, Any]] = []
        self._zone_counter = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            output_min = float(user_input[CONF_OUTPUT_MIN])
            output_max = float(user_input[CONF_OUTPUT_MAX])
            if output_max <= output_min:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_schema(user_input),
                    errors={CONF_OUTPUT_MAX: "max_must_exceed_min"},
                )

            self._config_data = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_OUTDOOR_ENTITY: user_input[CONF_OUTDOOR_ENTITY],
                CONF_FLOW_SENSOR_ENTITY: user_input.get(CONF_FLOW_SENSOR_ENTITY),
                CONF_AGGRESSIVENESS_ENTITY: user_input.get(CONF_AGGRESSIVENESS_ENTITY),
                CONF_DEFAULT_AGGRESSIVENESS: float(
                    user_input[CONF_DEFAULT_AGGRESSIVENESS]
                ),
                CONF_OUTPUT_MIN: output_min,
                CONF_OUTPUT_MAX: output_max,
                CONF_ACTIVE_MIN_FLOW: float(user_input[CONF_ACTIVE_MIN_FLOW]),
                CONF_UPDATE_INTERVAL: int(user_input[CONF_UPDATE_INTERVAL]),
                CONF_WEATHER_REF: float(user_input[CONF_WEATHER_REF]),
                CONF_WEATHER_SLOPE_ECO: float(user_input[CONF_WEATHER_SLOPE_ECO]),
                CONF_WEATHER_SLOPE_BOOST: float(user_input[CONF_WEATHER_SLOPE_BOOST]),
                CONF_WEATHER_OFFSET: float(user_input[CONF_WEATHER_OFFSET]),
            }
            return await self.async_step_zone()

        return self.async_show_form(step_id="user", data_schema=self._user_schema())

    async def async_step_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            zone = self._build_zone(user_input)
            zone_ids = {existing[CONF_ZONE_ID] for existing in self._zones}
            if zone[CONF_ZONE_ID] in zone_ids:
                return self.async_show_form(
                    step_id="zone",
                    data_schema=self._zone_schema(user_input=user_input),
                    errors={CONF_ZONE_ID: "zone_id_exists"},
                )

            self._zones.append(zone)
            if user_input.get("add_another", False):
                self._zone_counter += 1
                return self.async_show_form(
                    step_id="zone", data_schema=self._zone_schema()
                )

            data = dict(self._config_data)
            data[CONF_ZONES] = self._zones
            return self.async_create_entry(
                title=self._config_data[CONF_NAME], data=data
            )

        return self.async_show_form(step_id="zone", data_schema=self._zone_schema())

    def _user_schema(self, user_input: dict[str, Any] | None = None) -> vol.Schema:
        defaults = user_input or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=defaults.get(CONF_NAME, "Modulating thermostat")
                ): str,
                vol.Required(
                    CONF_OUTDOOR_ENTITY, default=defaults.get(CONF_OUTDOOR_ENTITY)
                ): ENTITY_SELECTOR,
                vol.Optional(
                    CONF_FLOW_SENSOR_ENTITY,
                    default=defaults.get(CONF_FLOW_SENSOR_ENTITY),
                ): ENTITY_SELECTOR,
                vol.Optional(
                    CONF_AGGRESSIVENESS_ENTITY,
                    default=defaults.get(CONF_AGGRESSIVENESS_ENTITY),
                ): ENTITY_SELECTOR,
                vol.Required(
                    CONF_DEFAULT_AGGRESSIVENESS,
                    default=defaults.get(
                        CONF_DEFAULT_AGGRESSIVENESS, DEFAULT_DEFAULT_AGGRESSIVENESS
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required(
                    CONF_OUTPUT_MIN,
                    default=defaults.get(CONF_OUTPUT_MIN, DEFAULT_OUTPUT_MIN),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_OUTPUT_MAX,
                    default=defaults.get(CONF_OUTPUT_MAX, DEFAULT_OUTPUT_MAX),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_ACTIVE_MIN_FLOW,
                    default=defaults.get(CONF_ACTIVE_MIN_FLOW, DEFAULT_ACTIVE_MIN_FLOW),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=600)),
                vol.Required(
                    CONF_WEATHER_REF,
                    default=defaults.get(CONF_WEATHER_REF, DEFAULT_WEATHER_REF),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_WEATHER_SLOPE_ECO,
                    default=defaults.get(
                        CONF_WEATHER_SLOPE_ECO, DEFAULT_WEATHER_SLOPE_ECO
                    ),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_WEATHER_SLOPE_BOOST,
                    default=defaults.get(
                        CONF_WEATHER_SLOPE_BOOST, DEFAULT_WEATHER_SLOPE_BOOST
                    ),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_WEATHER_OFFSET,
                    default=defaults.get(CONF_WEATHER_OFFSET, DEFAULT_WEATHER_OFFSET),
                ): vol.Coerce(float),
            }
        )

    def _zone_schema(self, user_input: dict[str, Any] | None = None) -> vol.Schema:
        defaults = user_input or {}
        default_zone_id = defaults.get(CONF_ZONE_ID, f"zone_{self._zone_counter}")
        return vol.Schema(
            {
                vol.Optional(CONF_ZONE_NAME, default=defaults.get(CONF_ZONE_NAME)): str,
                vol.Required(
                    CONF_ZONE_ID,
                    default=default_zone_id,
                ): vol.Match(r"^[a-zA-Z0-9_\-]+$"),
                vol.Required(
                    CONF_WEIGHT, default=defaults.get(CONF_WEIGHT, 1.0)
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0)),
                vol.Required(
                    CONF_TEMPERATURE_ENTITY,
                    default=defaults.get(CONF_TEMPERATURE_ENTITY),
                ): ENTITY_SELECTOR,
                vol.Required(
                    CONF_SETPOINT_ENTITY, default=defaults.get(CONF_SETPOINT_ENTITY)
                ): ENTITY_SELECTOR,
                vol.Optional(
                    CONF_ACTUATOR_ENTITY, default=defaults.get(CONF_ACTUATOR_ENTITY)
                ): ENTITY_SELECTOR,
                vol.Optional(
                    CONF_ACTUATOR_MIN, default=defaults.get(CONF_ACTUATOR_MIN, 0.0)
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_ACTUATOR_MAX, default=defaults.get(CONF_ACTUATOR_MAX, 100.0)
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_DEADBAND, default=defaults.get(CONF_DEADBAND, DEFAULT_DEADBAND)
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
                vol.Optional(
                    "add_another", default=defaults.get("add_another", False)
                ): bool,
            }
        )

    async def async_step_import(
        self, user_input: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        data = dict(user_input)
        zones: list[dict[str, Any]] = []
        for zone in data.get(CONF_ZONES, []):
            zone_copy = dict(zone)
            zone_copy[CONF_ZONE_ID] = slugify(zone_copy[CONF_ZONE_ID])
            zone_copy.setdefault(CONF_ZONE_NAME, zone_copy[CONF_ZONE_ID])
            zones.append(zone_copy)
        data[CONF_ZONES] = zones
        unique_id = slugify(data[CONF_NAME])
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates=data)
        return self.async_create_entry(title=data[CONF_NAME], data=data)

    def _build_zone(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Build a sanitized zone dict from form input."""
        zone_id = slugify(raw[CONF_ZONE_ID])
        zone_name = raw.get(CONF_ZONE_NAME) or zone_id
        zone: dict[str, Any] = {
            CONF_ZONE_ID: zone_id,
            CONF_ZONE_NAME: zone_name,
            CONF_WEIGHT: float(raw[CONF_WEIGHT]),
            CONF_TEMPERATURE_ENTITY: raw[CONF_TEMPERATURE_ENTITY],
            CONF_SETPOINT_ENTITY: raw[CONF_SETPOINT_ENTITY],
            CONF_DEADBAND: float(raw[CONF_DEADBAND]),
        }
        actuator_entity = raw.get(CONF_ACTUATOR_ENTITY)
        if actuator_entity:
            zone[CONF_ACTUATOR_ENTITY] = actuator_entity
            zone[CONF_ACTUATOR_MIN] = float(raw.get(CONF_ACTUATOR_MIN, 0.0))
            zone[CONF_ACTUATOR_MAX] = float(raw.get(CONF_ACTUATOR_MAX, 100.0))
        return zone

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return ModulatingThermostatOptionsFlow(config_entry)


class ModulatingThermostatOptionsFlow(config_entries.OptionsFlow):
    """Allow users to tweak behavioural options without redefining zones."""
    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        current: dict[str, Any] = dict(self.config_entry.data)
        current.update(self.config_entry.options)

        if user_input is not None:
            updated = dict(self.config_entry.options)
            updated.update(user_input)
            output_min = float(
                updated.get(
                    CONF_OUTPUT_MIN, current.get(CONF_OUTPUT_MIN, DEFAULT_OUTPUT_MIN)
                )
            )
            output_max = float(
                updated.get(
                    CONF_OUTPUT_MAX, current.get(CONF_OUTPUT_MAX, DEFAULT_OUTPUT_MAX)
                )
            )
            if output_max <= output_min:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._build_schema(current, user_input),
                    errors={CONF_OUTPUT_MAX: "max_must_exceed_min"},
                )
            return self.async_create_entry(title="", data=updated)

        return self.async_show_form(
            step_id="init",
            data_schema=self._build_schema(current, None),
        )

    def _build_schema(
        self,
        current: dict[str, Any],
        user_input: dict[str, Any] | None,
    ) -> vol.Schema:
        source = user_input or current
        return vol.Schema(
            {
                vol.Optional(
                    CONF_DEFAULT_AGGRESSIVENESS,
                    default=source.get(
                        CONF_DEFAULT_AGGRESSIVENESS,
                        current.get(
                            CONF_DEFAULT_AGGRESSIVENESS, DEFAULT_DEFAULT_AGGRESSIVENESS
                        ),
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Optional(
                    CONF_OUTPUT_MIN,
                    default=source.get(
                        CONF_OUTPUT_MIN,
                        current.get(CONF_OUTPUT_MIN, DEFAULT_OUTPUT_MIN),
                    ),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_OUTPUT_MAX,
                    default=source.get(
                        CONF_OUTPUT_MAX,
                        current.get(CONF_OUTPUT_MAX, DEFAULT_OUTPUT_MAX),
                    ),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_ACTIVE_MIN_FLOW,
                    default=source.get(
                        CONF_ACTIVE_MIN_FLOW,
                        current.get(CONF_ACTIVE_MIN_FLOW, DEFAULT_ACTIVE_MIN_FLOW),
                    ),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_WEATHER_SLOPE_ECO,
                    default=source.get(
                        CONF_WEATHER_SLOPE_ECO,
                        current.get(CONF_WEATHER_SLOPE_ECO, DEFAULT_WEATHER_SLOPE_ECO),
                    ),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_WEATHER_SLOPE_BOOST,
                    default=source.get(
                        CONF_WEATHER_SLOPE_BOOST,
                        current.get(
                            CONF_WEATHER_SLOPE_BOOST, DEFAULT_WEATHER_SLOPE_BOOST
                        ),
                    ),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_WEATHER_OFFSET,
                    default=source.get(
                        CONF_WEATHER_OFFSET,
                        current.get(CONF_WEATHER_OFFSET, DEFAULT_WEATHER_OFFSET),
                    ),
                ): vol.Coerce(float),
            }
        )
