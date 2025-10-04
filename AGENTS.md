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
