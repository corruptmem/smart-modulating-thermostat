# pyright: reportIncompatibleVariableOverride=false
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import ModulatingThermostatCoordinator
from .models import ControllerState, ZoneConfig


class TargetFlowSensor(
    CoordinatorEntity[ModulatingThermostatCoordinator], SensorEntity
):
    _attr_has_entity_name = True
    _attr_name = "Target flow temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ModulatingThermostatCoordinator) -> None:
        super().__init__(coordinator)
        slug = slugify(coordinator.config.name)
        self._attr_unique_id = f"{slug}_target_flow"
        self._attr_native_value = None
        self._attr_extra_state_attributes: dict[str, Any] = {}

    def _handle_coordinator_update(self) -> None:
        data = cast(ControllerState | None, self.coordinator.data)
        if data is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
        else:
            self._attr_native_value = round(data.target_flow_c, 2)
            zone_attrs = {
                zone_id: {
                    "temperature": info.temperature,
                    "target": info.target,
                    "error": info.error,
                    "demand": info.demand,
                    "actuator_ratio": info.actuator_ratio,
                    "weight_factor": info.weight_factor,
                    "actuator_target": info.actuator_target,
                }
                for zone_id, info in data.zone_diagnostics.items()
            }
            self._attr_extra_state_attributes = {
                "combined_demand": round(data.combined_demand, 3),
                "aggressiveness": round(data.aggressiveness, 3),
                "weather_target_c": round(data.weather_target_c, 2),
                "flow_sensor_c": data.flow_sensor_value,
                "outdoor_temperature_c": data.outdoor_temperature,
                "zones": zone_attrs,
            }
        super()._handle_coordinator_update()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ModulatingThermostatCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [TargetFlowSensor(coordinator)]
    for zone in coordinator.config.zones:
        if zone.actuator_entity:
            entities.append(ZoneActuatorTargetSensor(coordinator, zone))
    async_add_entities(entities)


class ZoneActuatorTargetSensor(
    CoordinatorEntity[ModulatingThermostatCoordinator], SensorEntity
):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: ModulatingThermostatCoordinator,
        zone: ZoneConfig,
    ) -> None:
        super().__init__(coordinator)
        self._zone: ZoneConfig = zone
        slug = slugify(f"{coordinator.config.name}_{zone.zone_id}")
        self._attr_unique_id = f"{slug}_actuator_target"
        self._attr_name = f"{zone.name} actuator target"
        self._attr_has_entity_name = False
        self._attr_native_unit_of_measurement = (
            PERCENTAGE
            if zone.actuator_min is None or zone.actuator_max is None
            else None
        )

    @property
    def native_value(self) -> float | None:
        data = cast(ControllerState | None, self.coordinator.data)
        if data is None:
            return None
        zone_diag = data.zone_diagnostics.get(self._zone.zone_id)
        if zone_diag is None or zone_diag.actuator_target is None:
            return None
        value = zone_diag.actuator_target
        return round(value, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = cast(ControllerState | None, self.coordinator.data)
        if data is None:
            return {}
        zone_diag = data.zone_diagnostics.get(self._zone.zone_id)
        if zone_diag is None:
            return {}
        return {
            "demand": zone_diag.demand,
            "actuator_ratio": zone_diag.actuator_ratio,
            "actuator_min": self._zone.actuator_min,
            "actuator_max": self._zone.actuator_max,
            "raw_temperature": zone_diag.temperature,
            "raw_target": zone_diag.target,
        }
