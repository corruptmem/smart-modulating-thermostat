from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import suppress
from datetime import timedelta
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .models import (
    ControllerConfig,
    ControllerState,
    ZoneDiagnostics,
    ZoneRuntime,
    controller_config_from_entry,
)
from .const import DOMAIN, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}

AGGRESSIVENESS_SCALE = 0.01
PID_KP_ECO = 0.4
PID_KP_BOOST = 1.0
PID_KI_ECO = 0.0008
PID_KI_BOOST = 0.003
INTEGRAL_MAX = 1.0
FLOW_KP = 0.2
FLOW_TRIM_MAX = 5.0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _lerp(a: float, b: float, factor: float) -> float:
    return (1.0 - factor) * a + factor * b


def _safe_float(state: StateType) -> float | None:
    """Best-effort conversion of Home Assistant states/attributes to float."""
    if state is None:
        return None
    if isinstance(state, (int, float)):
        return float(state)
    cleaned = str(state).strip()
    if cleaned.lower() in {"unknown", "unavailable", "none"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        match = re.search(r"[-+]?[0-9]*[.]?[0-9]+", cleaned.replace(",", "."))
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
    return None


def _resolve_log_level(config: ControllerConfig) -> int:
    """Map a configured log level string to a logging module constant."""
    default_level = logging.INFO
    candidate = getattr(config, "log_level", None)
    if candidate:
        return LOG_LEVELS.get(str(candidate).lower(), default_level)
    return default_level


class ModulatingThermostatCoordinator(DataUpdateCoordinator[ControllerState]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        entry_data: dict[str, Any],
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._config = controller_config_from_entry(entry_data)
        log_level = _resolve_log_level(self._config)
        slug = slugify(self._config.name)
        self._logger = logging.getLogger(f"{__name__}.{slug}")
        self._logger.setLevel(log_level)
        self._logger.debug(
            "Coordinator initialised with log level %s", logging.getLevelName(log_level)
        )
        self._store: Store[dict[str, Any]] | None = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}_{entry_id}.json",
            private=True,
        )
        self._save_task: asyncio.Task[None] | None = None
        update_interval = timedelta(seconds=self._config.update_interval)
        super().__init__(
            hass,
            self._logger,
            name=f"Modulating thermostat ({self._config.name})",
            update_interval=update_interval,
        )
        self._zone_runtime = {
            zone.zone_id: ZoneRuntime() for zone in self._config.zones
        }
        self._last_monotonic = time.monotonic()


    @property
    def config(self) -> ControllerConfig:
        return self._config

    async def _async_update_data(self) -> ControllerState:
        if not self._config.zones:
            raise UpdateFailed("No zones configured")

        now = time.monotonic()
        dt = now - self._last_monotonic
        if dt <= 0:
            dt = self._config.update_interval
        self._last_monotonic = now

        aggressiveness_raw = self._read_numeric_entity(
            self._config.aggressiveness_entity
        )
        if aggressiveness_raw is None:
            aggressiveness_raw = self._config.default_aggressiveness
        aggressiveness = _clamp(aggressiveness_raw * AGGRESSIVENESS_SCALE, 0.0, 1.0)
        self._logger.debug(
            "Aggressiveness raw=%.2f scaled=%.3f", aggressiveness_raw, aggressiveness
        )

        outdoor_temp = self._read_numeric_entity(self._config.outdoor_entity)
        flow_temp = self._read_numeric_entity(self._config.flow_sensor_entity)
        self._logger.debug(
            "Outdoor temperature=%s flow sensor=%s", outdoor_temp, flow_temp
        )

        zone_diagnostics: dict[str, ZoneDiagnostics] = {}
        total_weight = 0.0
        weighted_demand_sum = 0.0
        peak_demand = 0.0
        max_zone_weight = 0.0

        for zone in self._config.zones:
            zone_runtime = self._zone_runtime.setdefault(zone.zone_id, ZoneRuntime())
            diagnostics = ZoneDiagnostics()

            current_temp = self._read_numeric_entity(zone.temperature_entity)
            target_temp = self._read_numeric_entity(zone.setpoint_entity)
            diagnostics.temperature = current_temp
            diagnostics.target = target_temp

            if current_temp is None or target_temp is None:
                self._logger.debug(
                    "Zone %s skipped (temperature=%s target=%s)",
                    zone.zone_id,
                    current_temp,
                    target_temp,
                )
                zone_runtime.available = False
                zone_runtime.integral = 0.0
                zone_diagnostics[zone.zone_id] = diagnostics
                continue

            zone_runtime.available = True

            error = target_temp - current_temp
            if abs(error) <= zone.deadband:
                error = 0.0

            kp = _lerp(PID_KP_ECO, PID_KP_BOOST, aggressiveness)
            ki = _lerp(PID_KI_ECO, PID_KI_BOOST, aggressiveness)

            if error == 0.0:
                zone_runtime.integral *= 0.8
            else:
                zone_runtime.integral += error * dt
            integral_term = zone_runtime.integral * ki
            integral_term = _clamp(integral_term, -INTEGRAL_MAX, INTEGRAL_MAX)
            if ki > 0:
                zone_runtime.integral = integral_term / ki

            proportional_term = kp * error
            output = proportional_term + integral_term
            output = _clamp(output, 0.0, 1.0)

            actuator_ratio = 1.0
            actuator_target: float | None = None
            if zone.actuator_entity:
                actuator_value = self._read_numeric_entity(zone.actuator_entity)
                if (
                    actuator_value is not None
                    and zone.actuator_min is not None
                    and zone.actuator_max is not None
                    and zone.actuator_max > zone.actuator_min
                ):
                    actuator_ratio = _clamp(
                        (actuator_value - zone.actuator_min)
                        / (zone.actuator_max - zone.actuator_min),
                        0.0,
                        1.0,
                    )
                    diagnostics.actuator_ratio = actuator_ratio
                elif actuator_value is None:
                    diagnostics.actuator_ratio = None
                else:
                    actuator_ratio = 1.0
                    diagnostics.actuator_ratio = actuator_ratio
                if actuator_value is not None:
                    if zone.actuator_min is not None and zone.actuator_max is not None:
                        span = zone.actuator_max - zone.actuator_min
                        actuator_target = zone.actuator_min + output * span
                    else:
                        actuator_target = output * 100.0
                    self._logger.debug(
                        "Zone %s actuator target=%.3f (min=%s max=%s)",
                        zone.zone_id,
                        actuator_target,
                        zone.actuator_min,
                        zone.actuator_max,
                    )
            diagnostics.error = error
            diagnostics.demand = output

            weight_factor = zone.weight * actuator_ratio
            diagnostics.weight_factor = weight_factor
            if not zone.actuator_entity:
                diagnostics.actuator_ratio = actuator_ratio
            diagnostics.actuator_target = actuator_target

            self._logger.debug(
                "Zone %s: temp=%s target=%s error=%.3f demand=%.3f weight=%.3f actuator=%.3f",
                zone.zone_id,
                current_temp,
                target_temp,
                error,
                output,
                zone.weight,
                actuator_ratio,
            )

            total_weight += zone.weight
            weighted_demand_sum += zone.weight * output
            max_zone_weight = max(max_zone_weight, zone.weight)
            if max_zone_weight > 0:
                peak_candidate = output * (zone.weight / max_zone_weight)
            else:
                peak_candidate = 0.0
            peak_demand = max(peak_demand, peak_candidate)

            zone_diagnostics[zone.zone_id] = diagnostics

        combined_demand = 0.0
        if total_weight > 0:
            average_demand = weighted_demand_sum / total_weight
            combined_demand = _lerp(average_demand, peak_demand, aggressiveness)
            combined_demand = _clamp(combined_demand, 0.0, 1.0)
        else:
            average_demand = 0.0
        self._logger.debug(
            "Demand summary: avg=%.3f peak=%.3f combined=%.3f",
            average_demand,
            peak_demand,
            combined_demand,
        )

        reference_temp = self._config.weather_reference_temperature
        if outdoor_temp is not None:
            delta = max(reference_temp - outdoor_temp, 0.0)
        else:
            delta = reference_temp

        weather_slope = _lerp(
            self._config.weather_slope_eco,
            self._config.weather_slope_boost,
            aggressiveness,
        )
        weather_target = self._config.weather_offset + weather_slope * delta
        self._logger.debug(
            "Weather compensation: slope=%.3f delta=%.3f target=%.2f",
            weather_slope,
            delta,
            weather_target,
        )
        weather_target = _clamp(
            weather_target, self._config.output_min, self._config.output_max
        )

        if combined_demand <= 0:
            target_flow = self._config.output_min
        else:
            active_floor = max(self._config.output_min, self._config.active_min_flow)
            weather_limited = _clamp(
                weather_target, active_floor, self._config.output_max
            )
            target_flow = active_floor + (weather_limited - active_floor) * combined_demand
            headroom = self._config.output_max - weather_limited
            if headroom > 0:
                # Allow full-demand zones to climb beyond the weather curve without
                # permanently abandoning compensation for milder conditions.
                target_flow += headroom * combined_demand
            target_flow = _clamp(
                target_flow,
                self._config.output_min,
                self._config.output_max,
            )

        if flow_temp is not None:
            flow_error = target_flow - flow_temp
            flow_trim = _clamp(flow_error * FLOW_KP, -FLOW_TRIM_MAX, FLOW_TRIM_MAX)
            self._logger.debug(
                "Flow feedback: measured=%.2f target=%.2f error=%.2f trim=%.2f",
                flow_temp,
                target_flow,
                flow_error,
                flow_trim,
            )
            target_flow = _clamp(
                target_flow + flow_trim,
                self._config.output_min,
                self._config.output_max,
            )

        self._logger.debug(
            "Update complete: target_flow=%.2f aggressiveness=%.3f combined_demand=%.3f",
            target_flow,
            aggressiveness,
            combined_demand,
        )
        self._schedule_save_runtime()

        return ControllerState(
            target_flow_c=target_flow,
            combined_demand=combined_demand,
            aggressiveness=aggressiveness,
            weather_target_c=weather_target,
            zone_diagnostics=zone_diagnostics,
            flow_sensor_value=flow_temp,
            outdoor_temperature=outdoor_temp,
        )

    def _read_numeric_entity(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state_obj = self.hass.states.get(entity_id)
        if state_obj is None:
            self._logger.debug("Entity %s not found", entity_id)
            return None
        if state_obj.state in {"unknown", "unavailable", "None"}:
            self._logger.debug(
                "Entity %s state %s treated as unavailable", entity_id, state_obj.state
            )
            return None
        value = _safe_float(state_obj.state)
        if value is not None:
            self._logger.debug("Entity %s state=%s", entity_id, value)
            return value
        for key in ("temperature", "current_temperature", "value"):
            attr_val = state_obj.attributes.get(key)
            value = _safe_float(attr_val)
            if value is not None:
                self._logger.debug("Entity %s attribute %s=%s", entity_id, key, value)
                return value
        self._logger.debug(
            "Entity %s has no numeric value (state=%s attributes=%s)",
            entity_id,
            state_obj.state,
            state_obj.attributes,
        )
        return None

    async def async_load_runtime(self) -> None:
        """Restore persistent PI integrals from storage."""
        if self._store is None:
            return
        data: dict[str, Any] | None = await self._store.async_load()
        if not data:
            self._logger.debug("No persisted runtime state for %s", self._config.name)
            return
        zones = cast(dict[str, Any], data.get("zones", {}))
        for zone_id, zone_state in zones.items():
            runtime = self._zone_runtime.get(zone_id)
            if runtime is None:
                continue
            zone_dict = cast(dict[str, Any], zone_state)
            runtime.integral = float(zone_dict.get("integral", 0.0))
            self._logger.debug("Restored zone %s integral to %.6f", zone_id, runtime.integral)

    async def async_unload(self) -> None:
        """Cancel any pending persistence task during coordinator teardown."""
        if self._save_task:
            self._save_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._save_task
        self._save_task = None

    def _schedule_save_runtime(self) -> None:
        """Schedule a save of the current integrals once the event loop is idle."""
        if self._store is None:
            return
        if self._save_task and not self._save_task.done():
            return
        self._save_task = self.hass.async_create_task(self._async_save_runtime())

    async def _async_save_runtime(self) -> None:
        """Persist the integrals for each zone to Home Assistant storage."""
        if self._store is None:
            return
        payload: dict[str, Any] = {
            "zones": {
                zone_id: {"integral": runtime.integral}
                for zone_id, runtime in self._zone_runtime.items()
            }
        }
        try:
            await self._store.async_save(payload)
        except Exception as err:  # pragma: no cover - defensive
            self._logger.warning("Unable to persist runtime state: %s", err)


def merge_entry_data(entry: Any) -> dict[str, Any]:
    data = dict(entry.data)
    if entry.options:
        data.update(entry.options)
    return data
