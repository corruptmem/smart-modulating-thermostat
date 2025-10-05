# Information for agents

We are writing a home assistant integration for controlling a boiler based on thermostats.

## Coding Style & Naming Conventions

Format Python with Black and lint with Ruff; TypeScript uses Prettier + ESLint; firmware follows clang-format (LLVM). Stick to snake_case for backend modules, PascalCase for React components and C++ classes, and kebab-case for directories and feature flags. Run `pre-commit run --all-files` before every commit.

## Testing Guidelines

Name unit tests `test_<feature>.py` or `<component>.spec.ts` and keep fixtures under `tests/_data/`. Integration suites model thermostat behaviours (setpoints, safety lockouts) and use `@pytest.mark.integration`. Maintain ≥85% coverage with `pytest --cov=src` and `vitest run --coverage`.

## Commit & Pull Request Guidelines

Use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`) and keep subject lines ≤72 characters. Summaries should reference the subsystem touched and list validation commands (for example, `make test`, `platformio run`). Pull requests need a short narrative, linked issue/ticket, and screenshots for UI updates or telemetry diffs for firmware changes. Note any secrets or calibration updates and confirm lint/test status before requesting review.

## Security & Configuration Tips

Never commit `.env`

## Integration Snapshot (April 2025)

- **Entities**
  * `sensor.<controller>_target_flow_temperature` – exposes full diagnostics (per-zone demand, actuator ratio/target, weather target, flow feedback).
  * `sensor.<controller>_<zone>_actuator_target` – emitted for every zone specifying `actuator_entity`; units follow actuator range, defaults to %.
- **Persistence**
  * Zone PI integrals are saved to `.storage/modulating_thermostat_<entry>.json` after each update and restored on startup. Saves are async via HA’s `Store` helper.
- **Logging**
  * Controller config accepts `log_level` (`debug`/`info`/`warning`/`error`). Debug logging prints demand blending, weather compensation, actuator targets and entity parsing.
- **Demand behaviour**
  * Weather reset still produces a baseline target; when combined demand → 1.0 we now add headroom toward `output_max` so high-demand zones can drive maximum flow.
- **YAML import**
  * `modulating_thermostat:` can be a list or `{controllers: [...]}`. Config flow imports on startup and responds to “Reload YAML configuration”.
- **Tests**
  * `tests/test_control_loop.py` includes a persistence test that exercises the new storage hooks via dummy Store objects. Adjust when altering persistence internals.
- **Future work ideas**
  * Optional actuator write-back (service or automation hints).
  * UI card summarising per-zone targets.
  * Validation for actuator entity units / min-max sanity.
