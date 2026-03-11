# Implementation Plan: Custom HTTP Headers for Webhooks

**Branch**: `pmi-445-webhook-headers` | **Date**: 2026-03-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/infp-445-webhook-headers/spec.md`

## Summary

Add a generic `CoreKeyValue` hierarchy (static, password, environment-variable) and a many-to-many `headers` relationship on `CoreWebhook` so that custom HTTP headers are injected into every webhook request. Environment-variable headers resolve at send time on the Prefect worker. The webhook cache is extended to include serialized header data and invalidated when key-value nodes or their webhook relationships change.

## Technical Context

**Language/Version**: Python 3.12, TypeScript 5.9
**Primary Dependencies**: FastAPI 0.121.1, Pydantic 2.10, React 19.2, Neo4j 5.28
**Storage**: Neo4j graph database (branch-agnostic nodes)
**Testing**: pytest 9.0 (unit/functional/integration), Vitest 4.0, Playwright 1.56
**Target Platform**: Linux server (backend/workers), Web browser (frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: No measurable degradation to webhook send latency; header resolution < 10ms
**Constraints**: Headers cached alongside webhook data (2-hour TTL); environment variable resolution only on Prefect worker
**Scale/Scope**: Typically 1-20 headers per webhook; hundreds of webhooks max

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | New `CoreKeyValue` generic + 3 node types defined in schema layer; all writes validate against schema |
| II. Branch-Safe by Default | PASS | Key-value pairs are `branch=BranchSupportType.AGNOSTIC` matching webhook behavior |
| III. Type Safety & Explicit Contracts | PASS | Typed Pydantic models for cache serialization; frozen dataclasses for query results; GraphQL contracts defined before implementation |
| IV. Test Discipline | PASS | Unit tests for header resolution/merging, functional tests for end-to-end webhook+headers flow, E2E tests for UI |
| V. Query Performance & Efficiency | PASS | Batch-fetch headers per webhook via single Cypher query; no N+1 patterns |
| VI. Security & Input Boundaries | PASS | Password kind for sensitive headers (masked in UI/API); env var names validated; no secrets in logs |
| VII. Simplicity & Maintainability | PASS | Follows existing Generic→Node inheritance pattern (like CoreTransformation); reuses Password attribute kind; no new abstractions |

No violations. No complexity justifications needed.

### Post-Design Re-Check (Phase 1 complete)

| Principle | Status | Post-Design Notes |
|-----------|--------|-------------------|
| I. Schema-Driven Integrity | PASS | `data-model.md` defines all entities with attributes, relationships, and constraints. Schema definitions use `GenericSchema`/`NodeSchema` classes. |
| II. Branch-Safe by Default | PASS | All new entities are `AGNOSTIC`. Cache invalidation handles cross-branch scenarios (agnostic nodes are global). |
| III. Type Safety & Explicit Contracts | PASS | `contracts/graphql.md` defines all GraphQL types and mutations. `HeaderConfig` Pydantic model typed. No untyped dicts. |
| IV. Test Discipline | PASS | Test plan covers: unit (header merging, env var resolution), functional (webhook+headers E2E flow), E2E (UI configuration). |
| V. Query Performance & Efficiency | PASS | Headers fetched in batch during `convert_node_to_webhook`; cached alongside webhook data. No per-header queries at send time. |
| VI. Security & Input Boundaries | PASS | Password kind masks values. Env var names validated by regex. Header names validated against RFC 7230. No secrets in cache keys or logs. |
| VII. Simplicity & Maintainability | PASS | 1 new file (`key_value.py`), modifications to ~6 existing files. Reuses existing patterns throughout. No new abstractions or dependencies. |

## Project Structure

### Documentation (this feature)

```text
specs/infp-445-webhook-headers/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── graphql.md       # GraphQL schema additions
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── infrahub/core/schema/definitions/core/
│   ├── key_value.py                    # NEW: CoreKeyValue generic + 3 node schemas
│   └── webhook.py                      # MODIFIED: add headers relationship to CoreWebhook
├── infrahub/core/schema/definitions/core/__init__.py  # MODIFIED: register new schemas
├── infrahub/webhook/
│   ├── models.py                       # MODIFIED: add headers to Webhook model + cache
│   ├── tasks/process.py                # MODIFIED: resolve headers at send time
│   └── tasks/configure.py              # MODIFIED: cache invalidation for header changes
├── infrahub/webhook/triggers.py        # MODIFIED: add CoreKeyValue kinds to trigger match
└── tests/
    ├── unit/webhook/                   # NEW: header resolution, env var, merging tests
    └── functional/webhook/             # MODIFIED: add header-aware webhook tests

frontend/app/
└── tests/e2e/webhook/webhook.spec.ts   # MODIFIED: E2E test for header configuration
```

**Structure Decision**: Existing web application structure. New schema definition file `key_value.py` follows the established pattern (`transform.py`, `account.py`). All other changes modify existing files.
