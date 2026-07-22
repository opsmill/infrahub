# Implementation Plan: Re-enable ruff BLE (blind-except) rule and fix all violations

**Branch**: `pha/INBOX-19` | **Date**: 2026-07-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-ruff-ble-reenable/spec.md`

## Summary

Remove `"BLE"` from the global ruff ignore list in the root `pyproject.toml` and resolve all 78 current BLE001 violations (46 files) so the repo-wide CI lint gate (`uv run ruff check . --exclude python_sdk`) passes with the rule active. Each site receives exactly one of two treatments derived from a per-site analysis (see [data-model.md](data-model.md)): **narrow** the handler to the exception types the guarded code can actually raise, or **suppress** with a line-targeted `# noqa: BLE001` plus a truthful justification comment. Hard-constraint areas (graph migrations, authentication flows) are suppression-only — their runtime semantics must not change. No autofix exists for BLE001; every edit is manual and minimal, per the house `/fix-ruff-rule` method.

## Technical Context

**Language/Version**: Python 3.14 (backend), per root `pyproject.toml`; repo tooling (`tasks/`, `utilities/`, `tests/e2e/`) runs under the same toolchain

**Primary Dependencies**: ruff 0.15 (lint), invoke 2.2 (task runner), uv (env). No new dependencies permitted or needed

**Storage**: N/A — no data or schema changes; graph-migration files are edited annotation-only (comments + suppressions)

**Testing**: pytest 9.0 — backend unit tests (`uv run invoke backend.test-unit`) and targeted component tests for touched modules; heavier tiers (integration, e2e, scale) validate in CI as usual

**Target Platform**: Developer workstations + GitHub Actions CI (lint job runs `uv run ruff check . --exclude python_sdk`)

**Project Type**: Codebase-quality change to an existing monorepo (lint config + point edits across backend, backend tests, tasks, utilities, e2e helpers)

**Performance Goals**: N/A (no runtime-path changes; narrowed handlers have identical or marginally cheaper dispatch)

**Constraints**:
- No DB schema or migration semantic changes (migration files: annotation-only edits)
- No GraphQL/REST API contract changes; no auth behavior changes (auth files: annotation-only edits)
- No new dependencies, no CI workflow edits, no manual edits to generated files
- Preserve runtime behavior for all exception types the guarded code can actually raise; only genuinely-unexpected exception types may newly propagate, and only at narrowed non-constraint sites

**Scale/Scope**: 78 violation sites / 46 files, one config-line removal, zero new modules. Site inventory and per-site treatment matrix in [data-model.md](data-model.md)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Gate | Status |
|---|-----------|------|--------|
| I | Schema-Driven Integrity | No schema-layer or generated-file edits. | ✅ PASS — config + handler annotations only; generated dirs contain no violations |
| II | Branch-Safe by Default | No query or branch-logic changes. | ✅ PASS — no behavioral edits to branch-aware code paths |
| III | Type Safety & Explicit Contracts | Exception narrowing strengthens explicit contracts; mypy/ty must stay green. | ✅ PASS — narrowing names real exception types; `invoke backend.lint` (ruff+ty+mypy) is an exit gate |
| IV | Test Discipline | Existing tests must keep passing; no new feature surface needing new tests. | ✅ PASS — verification relies on existing suites + lint-gate mutation check (SC-006); no assertions change |
| V | Query Performance & Efficiency | No queries added or modified. | ✅ PASS |
| VI | Security & Input Boundaries | Auth error-handling semantics unchanged (suppression-only in auth files). | ✅ PASS — narrowing in auth paths is explicitly forbidden by plan policy |
| VII | Simplicity & Maintainability | Minimal diffs; no new abstractions or helpers. | ✅ PASS — per-site edits only; no shared "safe_catch" utility invented |

**Quality gates** (constitution §Development Workflow): format (`uv run invoke format` must produce no diff on touched files), lint (`uv run invoke backend.lint` + repo-wide ruff check), tests (touched-module suites), changelog (not required — internal housekeeping, no user-facing change; recorded in spec Assumptions).

**Post-design re-check (after Phase 1)**: ✅ PASS — design introduces no schema, query, auth, dependency, or generated-file changes; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-ruff-ble-reenable/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: rule semantics, house method, policy decisions
├── data-model.md        # Phase 1: full 78-site inventory with per-site treatment
├── quickstart.md        # Phase 1: validation guide (commands + expected outcomes)
├── checklists/
│   └── requirements.md  # Spec quality checklist (complete)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by /speckit-plan)
```

*(`specs/` is a symlink to `dev/specs/` — canonical git path is `dev/specs/002-ruff-ble-reenable/`.)*

### Source Code (repository root)

```text
pyproject.toml                                  # [tool.ruff.lint] ignore: remove "BLE" (~line 511)
backend/infrahub/
├── api/{auth,oauth2,oidc}.py                   # 4 sites — suppress (auth constraint)
├── auth/auth.py                                # 4 sites — suppress (auth constraint)
├── artifacts/tasks.py                          # 1 site
├── cli/upgrade.py                              # 2 sites
├── core/migrations/graph/m0*.py                # 27 sites — suppress (migration constraint)
├── core/migrations/shared.py                   # 3 sites — suppress (migration constraint)
├── core/schema/update_coordinator.py           # 2 sites
├── core/validators/tasks.py                    # 1 site
├── generators/tasks.py                         # 1 site
├── git/{integrator,sync}.py                    # 2 sites
├── message_bus/operations/__init__.py          # 1 site
├── services/scheduler.py                       # 1 site
├── task_manager/flow_run/retention.py          # 1 site
├── telemetry/tasks.py                          # 3 sites
└── webhook/tasks/process.py                    # 1 site
backend/tests/
├── component/core/schema/schema_branch/…       # 4 sites (2 files)
├── helpers/{diagnostics,events,test_worker}.py # 4 sites (incl. the BaseException handler)
├── integration/git/conftest.py                 # 2 sites
├── integration_docker/test_merge_kill_recovery.py # 1 site
└── scale/common/protocols.py                   # 2 sites
tasks/release.py                                # 2 sites
tests/e2e/data/parity.py                        # 1 site
utilities/infrahub_load_tester.py               # 8 sites
```

**Structure Decision**: No structural changes. The feature is a config-line removal plus point edits at the 78 inventoried handler sites listed above; the authoritative per-site treatment matrix lives in [data-model.md](data-model.md).

## Implementation Approach

1. **Fix order** (fail-fast, house method's ~10-file batches):
   1. Batch A — hard-constraint suppressions, migrations (30 sites, annotation-only).
   2. Batch B — hard-constraint suppressions, auth (8 sites, annotation-only).
   3. Batch C — backend runtime sites (16, per-site treatment from data-model.md).
   4. Batch D — backend test sites (13, incl. the `BaseException` handler decision).
   5. Batch E — tooling sites (11: `tasks/release.py`, `tests/e2e/data/parity.py`, `utilities/infrahub_load_tester.py`).
   6. Config flip — remove `"BLE"` from `pyproject.toml` ignore list (only after all sites are clean under `--select=BLE`).
2. **Per-batch verification**: `uv run ruff check --select=BLE <touched paths>` clean; `uv run ruff format --check` clean on touched files; batch-scoped tests where they exist.
3. **Final verification** (quickstart.md): repo-root `uv run ruff check --select=BLE .` → 0; `uv run ruff check . --exclude python_sdk` → 0; `uv run invoke backend.lint` → exit 0; mutation check (SC-006); diff audit of constraint areas (SC-007); touched-module unit/component tests.

Justification-comment style (from repo guideline `dev/guidelines/backend/python.md` §Exception Handling): comment states *why the broad catch is required at this boundary* (keep-alive loop, best-effort cleanup, per-item migration continuation, auth degradation), placed on or immediately above the `except` line; suppression is always `# noqa: BLE001` (line-targeted, rule-targeted).

## Complexity Tracking

> No constitution violations — table intentionally empty.
