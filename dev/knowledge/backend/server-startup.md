# Server Startup & Settings Validation

> Part of: `dev/knowledge/backend/` | Related: [architecture.md](architecture.md), [AGENTS.md](../../../backend/AGENTS.md)

How the Infrahub API server boots, where settings are validated, and why the entry points look the way they do. Read this before changing anything in `backend/infrahub/server.py`, `backend/infrahub/serve/`, or `backend/infrahub/cli/server.py`.

## The rule

An Infrahub process must never bind a socket or consume from a queue with an invalid configuration. If `Settings()` fails to instantiate the process exits with a clear error **before** the server is reachable.

## Entry points

| Launcher | Target | Where validation runs |
|---|---|---|
| `uvicorn --factory infrahub.server:create_app` | `create_app()` factory | First line of the factory, before `FastAPI(...)` is constructed |
| `gunicorn … infrahub.serve.app:app` | Module-level `app = create_app()` in `infrahub/serve/app.py` | Inside `create_app()` during module import + `on_starting` hook in `gunicorn_config.py` |
| `infrahub server start` (CLI) | Delegates to uvicorn with `factory=True` and `application = "infrahub.server:create_app"` | Same as uvicorn |
| `InfrahubWorkerAsync.setup()` (Prefect worker) | `workers/infrahub_async.py` | `config.SETTINGS.initialize_and_exit()` called unconditionally in `setup()` |
| `create_infrahub_prefect()` (Prefect server) | `prefect_server/app.py` | Only validates in distributed mode (when both `PREFECT_API_BLOCKS_REGISTER_ON_START=false` and `PREFECT_API_DATABASE_MIGRATE_ON_START=false`). Single-node Prefect does not need an Infrahub secret key. |

## Why two different gunicorn entry points (and no `preload_app`)

- **Why not use gunicorn's factory syntax `"infrahub.server:create_app()"` directly?** It works in plain shells but doesn't survive `sh -c "$COMMAND"` expansion used by `development/docker-compose.yml` — the embedded `"` characters end up as part of the module name (`ModuleNotFoundError: No module named '"infrahub'`). The two-line `infrahub/serve/app.py` launcher side-steps all shell quoting by exposing a plain `module:attribute` target.
- **Why not enable `preload_app = True` in `gunicorn_config.py`?** It would give fail-fast in the master for free, but `infrahub.worker.WORKER_IDENTITY` is a module-scope `str(uuid.uuid4())`. Preloading would make every forked worker inherit the same UUID, and workers would then collide when they each declare the exclusive RabbitMQ queue `api-callback-<id>`.
- **What we do instead**: `gunicorn_config.py` defines an `on_starting(server)` hook that calls `config.SETTINGS.initialize_and_exit()` in the master. Invalid config exits the master before any worker forks; when config is valid, workers fork fresh and each generates its own `WORKER_IDENTITY` at import time.

## Why settings are lazy in `config.py`

`Settings.security` is declared as `Field(default_factory=SecuritySettings)` instead of a direct `SecuritySettings()` at class scope. The class-scope form would call `SecuritySettings()` at class-definition time, so the `@field_validator` would fire the moment `infrahub.config` is imported — breaking every tool that imports `config` before it has a chance to set env vars (changelog generation, schema codegen, IDE helpers, …). The `default_factory` keeps the module importable; the factory is only executed when `Settings()` is instantiated, which is exactly when `load_and_exit()` is called from an entry point.

## Test surface

- `backend/tests/unit/config/test_security_settings.py::TestSecretKeyRequired` — direct `Settings()` / `SecuritySettings()` / `load()` validation.
- `backend/tests/unit/config/test_security_settings.py::TestFactoryValidation` — both factories (`create_app`, `create_infrahub_prefect`) positive + negative, including distributed-mode Prefect with `_init_prefect` mocked.

## Key files

- `backend/infrahub/server.py` — `create_app()` factory.
- `backend/infrahub/serve/app.py` — gunicorn launcher (`app = create_app()`).
- `backend/infrahub/serve/gunicorn_config.py` — `on_starting` hook, `preload_app` deliberately off.
- `backend/infrahub/cli/server.py` — CLI wrapper using `uvicorn.run(..., factory=True)`.
- `backend/infrahub/cli/dev.py` — offline codegen with `_load_settings_for_offline_codegen()`.
- `backend/infrahub/config.py` — `SecuritySettings`, `Settings`, `load()`, `load_and_exit()`, `ConfiguredSettings`.
- `backend/infrahub/prefect_server/app.py` — Prefect factory with conditional validation.
- `backend/infrahub/workers/infrahub_async.py` — worker `setup()` validation.
