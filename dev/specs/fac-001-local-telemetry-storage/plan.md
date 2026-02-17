# Implementation Plan: Local Telemetry Storage

**Branch**: `fac-001-local-telemetry-storage` | **Date**: 2026-02-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/fac-001-local-telemetry-storage/spec.md`

## Summary

Store daily telemetry JSON snapshots in the Neo4j database regardless of telemetry opt-out settings, ensuring air-gapped and opted-out customers retain usage data for support, auditing, and license compliance. The existing daily Prefect workflow (`send_telemetry_push`) will be modified to always persist a `TelemetrySnapshot` StandardNode locally before conditionally sending to the remote endpoint. A new `infrahubctl telemetry` CLI sub-command group provides export and list capabilities, and a REST API endpoint enables programmatic retrieval for future tech support bundle integration.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Pydantic, Neo4j (via `InfrahubDatabase`), Prefect (workflow orchestration), Typer/AsyncTyper (CLI), Rich (CLI output)
**Storage**: Neo4j graph database — `TelemetrySnapshot` as a `StandardNode` subclass (branch-agnostic, stored with `IS_PART_OF` relationship to Root)
**Testing**: pytest — unit tests for models/serialization, component tests for DB CRUD, functional tests for workflow + CLI
**Target Platform**: Linux server (containerized via Docker/Kubernetes)
**Project Type**: Web application (backend-only for this feature; no frontend changes)
**Performance Goals**: Daily collection + storage < 60 seconds; export of 5 years (~1825 records) < 2 minutes
**Constraints**: < 50 MB storage for 5 years of daily snapshots (~3-5 KB per snapshot ≈ ~6-9 MB total)
**Scale/Scope**: 1 snapshot/day, ~1825 records per 5 years, single JSON payload per record

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Schema-Driven Integrity | PASS | Telemetry snapshots are operational/system data (like Branch, Root), not user-schema data. Uses `StandardNode` pattern which stores directly in Neo4j without schema-layer governance. This is consistent with how Branch and Root nodes work. |
| II | Branch-Safe by Default | PASS | Telemetry snapshots are global system-level data, not branch-specific. They are stored as `StandardNode` with `IS_PART_OF` relationship to Root — same as Branch nodes. No branch or temporal filters needed. |
| III | Type Safety & Explicit Contracts | PASS | All code will use type hints. `TelemetrySnapshot` is a Pydantic `StandardNode` subclass. The telemetry payload is stored as a typed Pydantic model (`TelemetryData`), serialized to JSON. REST API contracts use Pydantic response models. |
| IV | Test Discipline | PASS | Unit tests for model serialization/deserialization. Component tests for StandardNode CRUD (create, get, get_list with date filtering). Functional tests for the modified Prefect workflow. CLI tested via subprocess invocation or Typer test client. |
| V | Query Performance & Efficiency | PASS | All queries are parameterized Cypher via `StandardNodeQuery` classes. Date-range filtering uses parameterized `WHERE` clauses on `created_at`. No N+1 patterns — single query returns all matching snapshots. Payload size ~3-5 KB per record. |
| VI | Security & Input Boundaries | PASS | Access to telemetry data requires `READ_TELEMETRY` global permission. REST endpoint uses `get_current_user` + `get_permission_manager` dependency injection. CLI commands connect via SDK client (inherits auth). No secrets in telemetry payloads. |
| VII | Simplicity & Maintainability | PASS | Reuses existing patterns: `StandardNode` for storage, `StandardNodeQuery` for queries, `AsyncTyper` for CLI, FastAPI dependency injection for REST. No new abstractions, frameworks, or dependencies. |

**Pre-Phase 0 Gate: PASS** — No violations. Proceeding to research.

## Project Structure

### Documentation (this feature)

```text
specs/fac-001-local-telemetry-storage/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── rest-api.md      # REST API contract
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/infrahub/
├── telemetry/
│   ├── constants.py          # (existing) Add snapshot-related constants
│   ├── models.py             # (existing) TelemetryData already defined
│   ├── tasks.py              # (modify) Add local storage to workflow
│   ├── database.py           # (existing) DB telemetry gathering
│   └── snapshot.py            # (new) TelemetrySnapshot StandardNode model
├── core/
│   └── constants/
│       └── __init__.py       # (modify) Add READ_TELEMETRY to GlobalPermissions
├── permissions/
│   └── constants.py          # (modify) Add denial message and description
├── api/
│   └── telemetry.py          # (new) REST API endpoint for telemetry retrieval
└── workflows/
    └── catalogue.py          # (existing) Workflow definition unchanged

python_sdk/infrahub_sdk/ctl/
├── cli_commands.py           # (modify) Register telemetry sub-app
└── telemetry.py              # (new) CLI commands: export, list

backend/tests/
├── unit/telemetry/
│   └── test_snapshot.py      # (new) Model serialization tests
├── component/telemetry/
│   └── test_snapshot_db.py   # (new) StandardNode CRUD tests
└── functional/telemetry/
    └── test_workflow.py       # (new) Workflow + storage tests
```

**Structure Decision**: Backend-only feature. Uses existing `backend/infrahub/telemetry/` module for the storage model and workflow changes. New CLI commands go in the SDK (`python_sdk/infrahub_sdk/ctl/telemetry.py`). REST API endpoint added to `backend/infrahub/api/`. Tests follow existing directory structure.

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design completion.*

| # | Principle | Status | Post-Design Notes |
|---|-----------|--------|-------------------|
| I | Schema-Driven Integrity | PASS | Confirmed: `TelemetrySnapshot` uses `StandardNode` pattern. No schema-layer interaction. Data model in `data-model.md` shows only Neo4j node properties and `IS_PART_OF` relationship to Root. |
| II | Branch-Safe by Default | PASS | Confirmed: No branch-specific queries. `StandardNodeGetListQuery` operates on all `TelemetrySnapshot` nodes globally. REST API does not accept branch parameters for telemetry data. |
| III | Type Safety & Explicit Contracts | PASS | Confirmed: `TelemetrySnapshot` fields are fully typed. REST API uses `TelemetrySnapshotResponse` and `TelemetrySnapshotListResponse` Pydantic models. CLI uses typed Typer parameters. `TelemetryData` payload preserves Pydantic typing through JSON serialization. |
| IV | Test Discipline | PASS | Confirmed: Three test levels planned — unit (model serialization), component (DB CRUD with Neo4j), functional (workflow integration). Test structure mirrors source layout. |
| V | Query Performance & Efficiency | PASS | Confirmed: Date-range filtering via parameterized Cypher `WHERE` clause on `created_at`. Single query pattern — no N+1. `StandardNodeGetListQuery` with `raw_filter` provides the extension point. Pagination via `limit`/`offset`. |
| VI | Security & Input Boundaries | PASS | Confirmed: `READ_TELEMETRY` global permission enforced at REST endpoint via `permission_manager.raise_for_permission()`. CLI uses SDK client (inherits JWT/API key auth). Date parameters validated by Pydantic. |
| VII | Simplicity & Maintainability | PASS | Confirmed: No new abstractions. 2 new files (`snapshot.py`, `api/telemetry.py`), 1 new CLI module (`ctl/telemetry.py`), 4 modified files. All follow established patterns. No new dependencies. |

**Post-Design Gate: PASS** — No violations found. Design is constitution-compliant.

## Complexity Tracking

No constitution violations — this section is intentionally empty.
