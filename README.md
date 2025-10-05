# Modulating Thermostat Integration for Home Assistant

This project provides a Home Assistant custom integration that implements a demand-weighted, multi-zone, weather-compensated controller for boilers (or other hydronic heat sources). It marshals temperature and setpoint entities from any number of zones, produces a target flow temperature, and exposes additional telemetry—including zone-level actuator targets—so you can drive valves/TRVs and diagnose behaviour without leaving Home Assistant.

- **Precise flow control** – Linear blend of weather-reset curve, per-zone PI controllers, and optional flow-sensor feedback keeps the target as low as possible while still satisfying demand.
- **Multi-zone weighting** – Each zone can define its importance and optional actuator range so critical rooms dominate the flow setpoint when needed.
- **Aggressiveness dial** – Map an `input_number` or other entity to trade efficiency for recovery speed; the controller smoothly interpolates between eco and boost curves.
- **Rich diagnostics** – Exposes per-zone temperature, setpoint, demand, and actuator targeting data; optional debug logging shows every intermediate calculation.
- **Persistence** – PI integrals are stored in `.storage/modulating_thermostat_<entry>.json`, so controllers pick up where they left off after Home Assistant restarts.

---

## Table of Contents

1. [Installation](#installation)
2. [Entities Exposed](#entities-exposed)
3. [Configuration](#configuration)
   * [UI Config Flow](#ui-config-flow)
   * [YAML Configuration](#yaml-configuration)
   * [Controller Options](#controller-options)
   * [Zone Options](#zone-options)
4. [Logging & Diagnostics](#logging--diagnostics)
5. [Behavioural Overview](#behavioural-overview)
   * [Demand Calculation](#demand-calculation)
   * [Weather Compensation](#weather-compensation)
   * [Actuator Targeting](#actuator-targeting)
6. [Persistence](#persistence)
7. [Development & Testing](#development--testing)
8. [Troubleshooting](#troubleshooting)

---

## Installation

1. **Copy the component** into your Home Assistant setup:
   ```bash
   ./scripts/deploy_to_home_assistant.sh user@ha-host:/config --reload-core --reload-entry
   ```
   The helper syncs `custom_components/modulating_thermostat/` and optionally triggers the Home Assistant reload services (requires `HA_BASE_URL` and `HA_TOKEN`).

2. **Restart Home Assistant** or reload YAML (Developer Tools → YAML → Reload YAML configuration) after deployment.

3. **Add the integration** via **Settings → Devices & Services → + Add Integration → Modulating Thermostat**. If you prefer YAML, define controllers under `modulating_thermostat` and the integration will import them at startup.

---

## Entities Exposed

For each controller named `Main Heating`, you will see:

- `sensor.main_heating_target_flow_temperature` – Read-only flow target (°C).
  * Attributes: combined demand, aggressiveness, weather target, flow feedback, outdoor temperature.
  * Per-zone attributes include the current measured temperature, setpoint, PI error/demand, actuator ratio, and `actuator_target` (desired actuator position in native units).
- `sensor.main_heating_<zone_id>_actuator_target` – Exposed for every zone with `actuator_entity` configured. Units match the actuator range (percentage when min/max are omitted).

These sensors are designed for dashboards, automations, and debugging. They do not attempt to control actuators directly—you remain in control of how the demand is applied.

---

## Configuration

### UI Config Flow

The config flow walks you through the following steps:

1. Select global controller options—outdoor sensor, optional flow sensor, aggressiveness helper, logging level, weather-reset parameters, and update interval.
2. Add one or more zones; for each zone you can specify sensors, weights, deadband, and optional actuator metadata.
3. Finish the flow; the integration immediately begins computing flow targets.

### YAML Configuration

You can define controllers in `configuration.yaml` (or any package include). The integration imports the controllers and reloads them when you trigger **Reload YAML configuration**.

```yaml
modulating_thermostat:
  - name: Main Heating Loop
    outdoor_entity: sensor.weather_outdoor_temperature
    flow_sensor_entity: sensor.boiler_flow_temperature
    aggressiveness_entity: input_number.heat_aggressiveness
    default_aggressiveness: 35.0
    output_min: 25.0
    output_max: 75.0
    active_min_flow: 35.0
    update_interval: 30
    weather_reference_temperature: 21.0
    weather_slope_eco: 1.2
    weather_slope_boost: 2.0
    weather_offset: 20.0
    log_level: debug
    zones:
      - zone_id: living_room
        name: Living Room
        weight: 1.5
        temperature_entity: sensor.living_room_temperature
        setpoint_entity: input_number.living_room_target
        deadband: 0.2
        actuator_entity: number.living_room_valve_position
        actuator_min: 0
        actuator_max: 100
      - zone_id: office
        name: Office
        weight: 3.0
        temperature_entity: sensor.office_temperature
        setpoint_entity: input_number.office_target
```

### Controller Options

| Key | Required | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | ✅ | string | – | Friendly controller name; drives entity IDs. |
| `outdoor_entity` | ✅ | entity | – | Outdoor temperature sensor used for weather reset. |
| `flow_sensor_entity` | ❌ | entity | `null` | Flow temperature sensor for feedback trimming. |
| `aggressiveness_entity` | ❌ | entity | `null` | Helper that scales aggressiveness 0–100%. |
| `default_aggressiveness` | ❌ | number | `50.0` | Aggressiveness percentage when helper is unavailable. |
| `output_min` | ❌ | °C | `25.0` | Minimum flow temperature. |
| `output_max` | ❌ | °C | `75.0` | Maximum flow temperature. |
| `active_min_flow` | ❌ | °C | `30.0` | Minimum flow when demand is non-zero. |
| `update_interval` | ❌ | seconds | `30` | Coordinator refresh interval. |
| `weather_reference_temperature` | ❌ | °C | `21.0` | Indoor reference used for outdoor delta. |
| `weather_slope_eco` | ❌ | number | `1.2` | Weather slope at 0 % aggressiveness. |
| `weather_slope_boost` | ❌ | number | `2.0` | Weather slope at 100 % aggressiveness. |
| `weather_offset` | ❌ | °C | `20.0` | Base flow setpoint when outdoor equals reference. |
| `log_level` | ❌ | string | `info` | Per-controller logging level (`debug`, `info`, `warning`, `error`). |
| `zones` | ✅ | list | – | Zone definitions (see below). |

### Zone Options

| Key | Required | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `zone_id` | ✅ | slug | – | Unique identifier for references and per-zone sensors. |
| `name` | ❌ | string | `zone_id` | Friendly name. |
| `weight` | ❌ | number | `1.0` | Relative priority of the zone. |
| `temperature_entity` | ✅ | entity | – | Current room temperature. |
| `setpoint_entity` | ✅ | entity | – | Desired setpoint (sensor, input_number, or climate attribute). |
| `deadband` | ❌ | °C | `0.1` | Zero-error zone around the setpoint. |
| `actuator_entity` | ❌ | entity | `null` | Valve/TRV position entity (output feedback). |
| `actuator_min` | ❌ | number | `0.0` | Actuator’s minimum raw value. |
| `actuator_max` | ❌ | number | `100.0` | Actuator’s maximum raw value. |

---

## Logging & Diagnostics

- Set `log_level: debug` on any controller to see detailed calculations in the Home Assistant log (zone demand, weather targets, flow feedback, actuator targeting).
- Each zone’s attributes include `actuator_ratio` (current valve position from the entity) and `actuator_target` (controller demand mapped into actuator units).
- Per-zone actuator target sensors mirror those values for easy automations/dashboards.

---

## Behavioural Overview

### Demand Calculation

1. Each zone runs a PI controller on the temperature error, honouring a zone-specific deadband to avoid jitter.
2. The controller scales each zone’s output by its weight and actuator availability, blending average versus peak demand according to aggressiveness.
3. Combined demand ranges from 0–1.

### Weather Compensation

- A blended slope (between eco and boost) shapes the outdoor-reset curve.
- When combined demand is full, the controller now builds on the weather curve and pushes toward `output_max`, ensuring high demand rooms receive as much heat as configured.

### Actuator Targeting

- If a zone defines `actuator_entity`, the controller calculates the desired actuator value in the entity’s native range and publishes it to `sensor.<controller>_<zone>_actuator_target`.
- Even without actuator feedback, the zone demand is scaled into 0–100% for easy use.

---

## Persistence

- Zone integrals are stored in `.storage/modulating_thermostat_<entry_id>.json`.
- On startup we reload the integrals so PI controllers resume without wind-up loss.
- The store is compact (just the integrals) and updates asynchronously after each calculation pass.

---

## Development & Testing

Clone the repo and run the usual checks:

```bash
uv run pyright
uv run python -m ruff check
uv run pytest
```

Coverage focuses on the core control loop (diagnostics exclude the simple HA plumbing). Feel free to contribute additional tests if you extend the integration.

---

## Troubleshooting

- **Flow target stuck low** – Increase `output_max`, confirm aggressiveness entity is reaching 100%, and check the logs for a zone still reporting `None` (missing sensor data).
- **Zone diagnostics are `null`** – Ensure both temperature and setpoint entities report numeric states (use template helpers for climate attributes), and confirm `log_level: debug` to see parser failures.
- **Actuator target missing** – Verify the zone has `actuator_entity` plus `actuator_min/max`; the integration exposes per-zone sensors only when those values are supplied.
- **Reload does nothing** – Make sure you added the integration via the UI at least once; YAML definitions are imported into config entries, and the standard “Reload YAML configuration” button applies changes thereafter.

---

Happy heating! If you have ideas or issues, open an issue or PR. We welcome contributions that improve the controller, add device classes, or extend diagnostics further.
