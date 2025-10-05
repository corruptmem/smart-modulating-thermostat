from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import (
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
)


@dataclass(slots=True)
class ZoneConfig:
    zone_id: str
    name: str
    weight: float
    temperature_entity: str
    setpoint_entity: str
    actuator_entity: str | None
    actuator_min: float | None
    actuator_max: float | None
    deadband: float


@dataclass(slots=True)
class ZoneRuntime:
    integral: float = 0.0
    available: bool = False


@dataclass(slots=True)
class ZoneDiagnostics:
    temperature: float | None = None
    target: float | None = None
    error: float | None = None
    demand: float | None = None
    actuator_ratio: float | None = None
    weight_factor: float | None = None
    actuator_target: float | None = None


def _zone_list_factory() -> list[ZoneConfig]:
    return []


@dataclass(slots=True)
class ControllerConfig:
    name: str
    outdoor_entity: str
    flow_sensor_entity: str | None
    aggressiveness_entity: str | None
    default_aggressiveness: float
    output_min: float
    output_max: float
    active_min_flow: float
    update_interval: float
    weather_reference_temperature: float
    weather_slope_eco: float
    weather_slope_boost: float
    weather_offset: float
    log_level: str | None = None
    zones: list[ZoneConfig] = field(default_factory=_zone_list_factory)


@dataclass(slots=True)
class ControllerState:
    target_flow_c: float
    combined_demand: float
    aggressiveness: float
    weather_target_c: float
    zone_diagnostics: dict[str, ZoneDiagnostics]
    flow_sensor_value: float | None
    outdoor_temperature: float | None


def zone_from_dict(data: dict[str, Any]) -> ZoneConfig:
    return ZoneConfig(
        zone_id=data["zone_id"],
        name=data.get("name", data["zone_id"]),
        weight=float(data["weight"]),
        temperature_entity=data["temperature_entity"],
        setpoint_entity=data["setpoint_entity"],
        actuator_entity=data.get("actuator_entity"),
        actuator_min=(
            float(data["actuator_min"])
            if data.get("actuator_min") is not None
            else None
        ),
        actuator_max=(
            float(data["actuator_max"])
            if data.get("actuator_max") is not None
            else None
        ),
        deadband=float(data.get("deadband", DEFAULT_DEADBAND)),
    )


def controller_config_from_entry(data: dict[str, Any]) -> ControllerConfig:
    raw_zones = data.get("zones", [])
    zones = [zone_from_dict(zone) for zone in raw_zones]
    return ControllerConfig(
        name=data["name"],
        outdoor_entity=data["outdoor_entity"],
        flow_sensor_entity=data.get("flow_sensor_entity"),
        aggressiveness_entity=data.get("aggressiveness_entity"),
        default_aggressiveness=float(
            data.get("default_aggressiveness", DEFAULT_DEFAULT_AGGRESSIVENESS)
        ),
        output_min=float(data.get("output_min", DEFAULT_OUTPUT_MIN)),
        output_max=float(data.get("output_max", DEFAULT_OUTPUT_MAX)),
        active_min_flow=float(data.get("active_min_flow", DEFAULT_ACTIVE_MIN_FLOW)),
        update_interval=float(data.get("update_interval", DEFAULT_UPDATE_INTERVAL)),
        weather_reference_temperature=float(
            data.get("weather_reference_temperature", DEFAULT_WEATHER_REF)
        ),
        weather_slope_eco=float(
            data.get("weather_slope_eco", DEFAULT_WEATHER_SLOPE_ECO)
        ),
        weather_slope_boost=float(
            data.get("weather_slope_boost", DEFAULT_WEATHER_SLOPE_BOOST)
        ),
        weather_offset=float(data.get("weather_offset", DEFAULT_WEATHER_OFFSET)),
        log_level=(
            str(data.get("log_level")).lower()
            if data.get("log_level") is not None
            else None
        ),
        zones=zones,
    )
