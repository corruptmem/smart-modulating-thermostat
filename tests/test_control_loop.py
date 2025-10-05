# pyright: reportPrivateUsage=none
from __future__ import annotations

import asyncio
import logging
import time
from math import isclose
from typing import Any, Coroutine, Tuple, cast

import pytest
from homeassistant.core import State

from custom_components.modulating_thermostat.coordinator import (
    ModulatingThermostatCoordinator,
    merge_entry_data,
)
from custom_components.modulating_thermostat.models import (
    ControllerState,
    ZoneRuntime,
    controller_config_from_entry,
)


def assert_close(
    actual: float,
    expected: float,
    *,
    rel: float | None = None,
    abs_tol: float | None = None,
) -> None:
    rel_tol = rel if rel is not None else 1e-9
    abs_t = abs_tol if abs_tol is not None else 0.0
    assert isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_t)


class FakeHass:
    def __init__(self, states: dict[str, State]) -> None:
        self.states = states

    def async_create_task(
        self, coro: Coroutine[Any, Any, Any]
    ) -> asyncio.Task[Any]:
        return asyncio.create_task(coro)


async def run_controller(
    entry_data: dict[str, Any],
    states: dict[str, State],
) -> Tuple[ModulatingThermostatCoordinator, ControllerState]:
    config = controller_config_from_entry(entry_data)
    coordinator = ModulatingThermostatCoordinator.__new__(
        ModulatingThermostatCoordinator
    )
    coordinator.hass = cast(Any, FakeHass(states))
    coordinator._logger = logging.getLogger("modulating_thermostat.test")
    coordinator._logger.setLevel(logging.DEBUG)
    coordinator._config = config
    coordinator._zone_runtime = {zone.zone_id: ZoneRuntime() for zone in config.zones}
    coordinator._last_monotonic = time.monotonic() - config.update_interval
    coordinator._entry_id = "test"
    coordinator._store = None
    coordinator._save_task = None
    result = await ModulatingThermostatCoordinator._async_update_data(coordinator)
    return coordinator, result


@pytest.mark.asyncio
async def test_target_flow_rises_with_zone_demand():
    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "default_aggressiveness": 50,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 1.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.1,
            }
        ],
    }

    states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "19.0"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "21.0"),
        "sensor.outdoor": State("sensor.outdoor", "5.0"),
    }

    _, result = await run_controller(entry, states)

    assert_close(result.combined_demand, 1.0, abs_tol=1e-3)
    assert_close(result.target_flow_c, 75.0, abs_tol=1e-6)


@pytest.mark.asyncio
async def test_zero_demand_holds_minimum_flow():
    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "default_aggressiveness": 50,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 1.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.1,
            }
        ],
    }

    states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "21.6"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "21.0"),
        "sensor.outdoor": State("sensor.outdoor", "5.0"),
    }

    _, result = await run_controller(entry, states)

    assert result.combined_demand == 0.0
    assert_close(result.target_flow_c, entry["output_min"], abs_tol=1e-6)


@pytest.mark.asyncio
async def test_flow_sensor_trim_adjusts_target():
    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "flow_sensor_entity": "sensor.flow",
        "default_aggressiveness": 50,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 1.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.1,
            }
        ],
    }

    states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "19.0"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "21.0"),
        "sensor.outdoor": State("sensor.outdoor", "5.0"),
        "sensor.flow": State("sensor.flow", "40.0"),
    }

    _, result = await run_controller(entry, states)

    assert_close(result.combined_demand, 1.0, abs_tol=1e-3)
    assert_close(result.target_flow_c, 75.0, abs_tol=1e-6)


@pytest.mark.asyncio
async def test_deadband_zero_error():
    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "default_aggressiveness": 50,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 1.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.5,
            }
        ],
    }

    states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "20.6"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "20.8"),
        "sensor.outdoor": State("sensor.outdoor", "5.0"),
    }

    _, result = await run_controller(entry, states)
    diagnostics = result.zone_diagnostics["living"]

    assert diagnostics.error == 0.0
    assert result.combined_demand == 0.0


@pytest.mark.asyncio
async def test_actuator_missing_state_sets_none():
    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "default_aggressiveness": 50,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 1.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.1,
                "actuator_entity": "number.living_valve",
                "actuator_min": 0.0,
                "actuator_max": 100.0,
            }
        ],
    }

    states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "19.0"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "21.0"),
        "sensor.outdoor": State("sensor.outdoor", "5.0"),
    }

    _, result = await run_controller(entry, states)
    diagnostics = result.zone_diagnostics["living"]

    assert diagnostics.actuator_ratio is None


@pytest.mark.asyncio
async def test_outdoor_missing_uses_reference_delta():
    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "default_aggressiveness": 0,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.0,
        "weather_slope_boost": 1.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 1.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.1,
            }
        ],
    }

    states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "19.0"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "21.0"),
    }

    _, result = await run_controller(entry, states)

    assert result.outdoor_temperature is None
    assert_close(result.weather_target_c, 41.0, abs_tol=1e-6)


@pytest.mark.asyncio
async def test_read_numeric_entity_handles_invalid():
    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "default_aggressiveness": 50,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 1.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.1,
            }
        ],
    }

    states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "19.0"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "21.0"),
        "sensor.outdoor": State("sensor.outdoor", "bad"),
    }

    coordinator, _ = await run_controller(entry, states)
    cast(Any, coordinator.hass).states["sensor.outdoor"] = State(
        "sensor.outdoor", "unknown"
    )

    assert coordinator._read_numeric_entity("sensor.outdoor") is None
    assert coordinator._read_numeric_entity("sensor.missing") is None
    assert coordinator._read_numeric_entity(None) is None


@pytest.mark.asyncio
async def test_update_fails_when_no_zones():
    from homeassistant.helpers.update_coordinator import UpdateFailed

    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "default_aggressiveness": 50,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [],
    }

    states: dict[str, State] = {
        "sensor.outdoor": State("sensor.outdoor", "5.0"),
    }

    coordinator = ModulatingThermostatCoordinator.__new__(
        ModulatingThermostatCoordinator
    )
    coordinator.hass = cast(Any, FakeHass(states))
    coordinator._logger = logging.getLogger("modulating_thermostat.test")
    coordinator._logger.setLevel(logging.DEBUG)
    coordinator._config = controller_config_from_entry(entry)
    coordinator._zone_runtime = {}
    coordinator._last_monotonic = time.monotonic()
    coordinator._entry_id = "test"
    coordinator._store = None
    coordinator._save_task = None

    with pytest.raises(UpdateFailed):
        await ModulatingThermostatCoordinator._async_update_data(coordinator)


def test_merge_entry_data_prefers_options():
    class Entry:  # minimal stub
        data = {"output_min": 25.0}
        options = {"output_min": 35.0, "new": 1}

    merged = merge_entry_data(Entry())
    assert merged["output_min"] == 35.0
    assert merged["new"] == 1


@pytest.mark.asyncio
async def test_runtime_state_persistence():
    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "default_aggressiveness": 50,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 1.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.1,
            }
        ],
    }

    states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "19.0"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "21.0"),
        "sensor.outdoor": State("sensor.outdoor", "5.0"),
    }

    coordinator, _ = await run_controller(entry, states)

    class DummyStore:
        def __init__(self, payload: dict[str, Any] | None = None) -> None:
            self._payload = payload
            self.saved: dict[str, Any] | None = None

        async def async_load(self) -> dict[str, Any] | None:
            return self._payload

        async def async_save(self, data: dict[str, Any]) -> None:
            self.saved = data

    coordinator._store = cast(
        Any, DummyStore({"zones": {"living": {"integral": 2.5}}})
    )
    await coordinator.async_load_runtime()
    assert coordinator._zone_runtime["living"].integral == 2.5

    save_store = DummyStore()
    coordinator._store = cast(Any, save_store)
    coordinator._zone_runtime["living"].integral = 4.5
    coordinator._schedule_save_runtime()
    if coordinator._save_task:
        await coordinator._save_task
    assert save_store.saved is not None
    assert save_store.saved["zones"]["living"]["integral"] == 4.5


@pytest.mark.asyncio
async def test_actuator_ratio_reflected_in_diagnostics():
    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "default_aggressiveness": 50,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 1.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.1,
                "actuator_entity": "number.living_valve",
                "actuator_min": 10.0,
                "actuator_max": 30.0,
            }
        ],
    }

    states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "19.5"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "21.0"),
        "sensor.outdoor": State("sensor.outdoor", "5.0"),
        "number.living_valve": State("number.living_valve", "20.0"),
    }

    _, result = await run_controller(entry, states)

    diagnostics = result.zone_diagnostics["living"]
    assert diagnostics.actuator_ratio is not None
    assert diagnostics.weight_factor is not None
    assert_close(diagnostics.actuator_ratio, 0.5, abs_tol=1e-3)
    assert_close(diagnostics.weight_factor, 0.5, abs_tol=1e-3)


@pytest.mark.asyncio
async def test_missing_sensor_skips_zone_without_crash():
    entry: dict[str, Any] = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "default_aggressiveness": 50,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 1.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.1,
            },
            {
                "name": "Bedroom",
                "zone_id": "bedroom",
                "weight": 1.0,
                "temperature_entity": "sensor.bedroom_temp",
                "setpoint_entity": "input_number.bedroom_setpoint",
                "deadband": 0.1,
            },
        ],
    }

    states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "19.0"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "21.0"),
        "input_number.bedroom_setpoint": State("input_number.bedroom_setpoint", "21.0"),
        "sensor.outdoor": State("sensor.outdoor", "5.0"),
    }

    _, result = await run_controller(entry, states)

    assert "bedroom" in result.zone_diagnostics
    assert result.zone_diagnostics["bedroom"].temperature is None
    assert_close(result.combined_demand, 1.0, abs_tol=1e-3)


@pytest.mark.asyncio
async def test_aggressiveness_biases_peak_demand():
    base_entry = {
        "name": "Boiler",
        "outdoor_entity": "sensor.outdoor",
        "aggressiveness_entity": "input_number.aggressiveness",
        "default_aggressiveness": 10,
        "output_min": 25.0,
        "output_max": 75.0,
        "active_min_flow": 30.0,
        "update_interval": 30,
        "weather_reference_temperature": 21.0,
        "weather_slope_eco": 1.2,
        "weather_slope_boost": 2.0,
        "weather_offset": 20.0,
        "zones": [
            {
                "name": "Living",
                "zone_id": "living",
                "weight": 2.0,
                "temperature_entity": "sensor.living_temp",
                "setpoint_entity": "input_number.living_setpoint",
                "deadband": 0.1,
            },
            {
                "name": "Bedroom",
                "zone_id": "bedroom",
                "weight": 1.0,
                "temperature_entity": "sensor.bedroom_temp",
                "setpoint_entity": "input_number.bedroom_setpoint",
                "deadband": 0.1,
            },
        ],
    }

    low_states: dict[str, State] = {
        "sensor.living_temp": State("sensor.living_temp", "19.0"),
        "input_number.living_setpoint": State("input_number.living_setpoint", "21.0"),
        "sensor.bedroom_temp": State("sensor.bedroom_temp", "20.6"),
        "input_number.bedroom_setpoint": State("input_number.bedroom_setpoint", "21.0"),
        "sensor.outdoor": State("sensor.outdoor", "5.0"),
        "input_number.aggressiveness": State("input_number.aggressiveness", "0"),
    }

    high_states: dict[str, State] = dict(low_states)
    high_states["input_number.aggressiveness"] = State(
        "input_number.aggressiveness", "100"
    )

    _, low_result = await run_controller(base_entry, low_states)
    _, high_result = await run_controller(base_entry, high_states)

    assert low_result.combined_demand < high_result.combined_demand
    assert_close(high_result.combined_demand, 1.0, abs_tol=1e-2)
