# Contract: Release-orchestration invoke tasks

After this change, no release task reads `[project].version` (it no longer exists). The
version input is **installed metadata** (`importlib.metadata.version("infrahub-server")`,
OQ-4/FR-017).

## Removed

- `tasks/utils.py::get_version_from_pyproject()` — removed once callers reworked (FR-009/010).
- `tasks/utils.py::project_ver()` — removed; zero callers (FR-010).
- `tasks/utils.py` `tomllib`/`tomli` import block — removed once both functions are gone (FR-010).
- `tasks/release.py::update_test_containers` — removed; testcontainers shares the version by
  construction (FR-016).

## Reworked — `update_helm_chart(context, chart_repo="helm/")`

- **Input**: installed metadata instead of `get_version_from_pyproject()` (was `release.py:114`).
- **Behavior preserved**: same `appVersion`/`version`/`values.yaml` `prefectTag` updates;
  `infrahub-enterprise` `infrahub` dependency update (`:184-191`); existing strict-greater +
  non-prerelease gate (`:141`).
- **Output**: identical to today for an equivalent release.

## Reworked — `update_docker_compose(context, docker_file="docker-compose.yml")`

- **Input**: installed metadata (was `release.py:204`).
- **Change (FR-022)**: tighten the version comparison from `if old_version != version`
  (`:228`) to strict-greater, matching `update_helm_chart` — never rewrite image tags
  downward for a maintenance release.
- **Output**: same image-tag updates for services `infrahub-server`, `task-worker`,
  `task-manager`.

## Shared helper

Introduce a single small helper (e.g. in `tasks/utils.py`) returning
`importlib.metadata.version("infrahub-server")`, consumed by both tasks. Keep
`packaging.version.Version` for comparison/prerelease logic. Full type hints (Principle III).

## Invariant

Both reworked tasks MUST be safe to invoke from the FR-019 tag-push workflow context, where
the package has been `uv sync`'d to the tag-derived version before the task runs.
