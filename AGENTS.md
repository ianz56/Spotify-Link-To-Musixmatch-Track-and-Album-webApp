# Repository Guidelines

## Project Structure & Module Organization
- `app.py` is the main Flask entry point; it exposes `asgi_app` for Hypercorn.
- `spotify.py`, `apple.py`, `mxm.py` implement provider logic; `Asyncmxm/` is an async Musixmatch client package.
- `templates/` contains Jinja HTML views; `static/` holds CSS/JS/assets.
- `translations/` stores locale files (`.po/.mo`) used by Flask-Babel; translation helpers live in `*translations.py` scripts.
- `tests/` contains pytest unit tests; `test_integration.py` is a standalone integration test.

## Build, Test, and Development Commands
- `pip install -r requirements-dev.txt` installs dev tooling (ruff, pytest, pre-commit).
- `pip install -r requirements.txt` installs runtime dependencies.
- `python app.py` runs the app locally via Hypercorn (uses `asgi_app`).
- `docker compose up --build` runs the containerized app on `http://localhost:8555`.
- `pre-commit run --all-files` runs lint/format hooks.

## Coding Style & Naming Conventions
- Python targets 3.12; follow `ruff` for linting and formatting (line length 88, double quotes).
- Use `snake_case` for functions/variables and `PascalCase` for classes.
- Jinja templates follow `djlint` rules (2-space indentation).

## Testing Guidelines
- Tests use `pytest`; run with `python -m pytest tests/`.
- Place new tests in `tests/` and name files `test_*.py`.
- Mock external APIs and environment variables; see `tests/test_spotify.py` for patterns.

## Commit & Pull Request Guidelines
- Commit history uses Conventional Commit prefixes (`feat:`, `fix:`, `chore(deps):`) and often includes PR numbers like `(#34)`.
- Keep commits scoped and descriptive; include dependency bumps under `chore(deps):`.
- PRs should describe the change, note impacted endpoints/templates, and include screenshots for UI updates.

## Configuration & Secrets
- App reads env vars like `secret_key`, `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, and Redis settings.
- For local dev, set `FLASK_ENV=development`; production requires `secret_key`.

## Translations
- Update existing locales in `translations/<lang>/LC_MESSAGES/messages.po` and run `python compile_translations.py`.
- Add languages via `python add_language.py <lang>` and update `app.py` + templates.
- When adding new strings, run `python extract_messages.py` then `pybabel update -i messages.pot -d translations`.
