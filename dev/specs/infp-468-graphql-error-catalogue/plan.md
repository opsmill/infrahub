# Implementation Plan: Enriched GraphQL Error Catalogue

**Branch**: `pog-infp-468-initial-error-conversion` | **Date**: 2026-05-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/infp-468-graphql-error-catalogue/spec.md`
**Companion**: [discovery.md](./discovery.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

## Summary

Introduce an authoritative Python error catalogue inside the Infrahub backend that maps a stable string identifier (e.g. `NODE_NOT_FOUND`, `PERMISSION_DENIED`) to a strongly-typed Pydantic `data` payload. Surface the catalogue on GraphQL error responses through `extensions.code` (string) + `extensions.http_status` (int) + `extensions.data` (typed), via a custom graphql-core error formatter installed on `InfrahubGraphQLApp`. Update the existing FastAPI exception handler so the `/graphql` auth-short-circuit path emits the new shape while `/api/...` REST responses keep their current wire format. Publish the catalogue as a machine-readable JSON Schema file; from that schema, generate TypeScript bindings in this repo (with a CI sync check) and let the SDK repo generate its own Python bindings via cross-repo workflow. Migrate the two existing frontend integer-code consumers (`graphqlClientApollo.tsx`, `pages/login.tsx`) in the same release.

v1 ships the nine codes agreed in spec FR-005: `NODE_NOT_FOUND`, `AUTHENTICATION_REQUIRED`, `TOKEN_EXPIRED`, `PERMISSION_DENIED`, `ATTRIBUTE_REQUIRED`, `ATTRIBUTE_INVALID_TYPE`, `ATTRIBUTE_CONSTRAINT_VIOLATION`, `BRANCH_NOT_FOUND`, `SCHEMA_NOT_FOUND`. Uncovered errors degrade to `UNDEFINED_ERROR` so every GraphQL error response carries `extensions.code` without exception.

## Technical Context

**Language/Version**: Python 3.12 (backend, SDK), TypeScript 5.9 (frontend)
**Primary Dependencies**:
- Backend: FastAPI 0.131, Graphene + graphql-core (custom `format_error`), Pydantic 2.12 (catalogue payload models + JSON Schema export), structlog (FR-018 telemetry).
- Frontend: React 19.2, Apollo Client (already wired via `graphqlClientApollo.tsx`), `json-schema-to-typescript` (new dev dep, ~ small) for binding generation.
- Tooling: Invoke 2.2 (new tasks `backend.export-error-catalogue`, `frontend.regenerate-error-bindings`, `frontend.check-error-bindings`).
**Storage**: N/A — no database schema, no migration. The catalogue is in-process Python data exported to a build artefact.
**Testing**: pytest (unit + functional), Vitest (frontend unit), Playwright (E2E for US2 multi-field form + permission routing).
**Target Platform**: Linux server (backend), evergreen browsers (frontend), Python 3.10+ (SDK consumers).
**Project Type**: Web application (backend + frontend). SDK is a Git submodule whose contents are not modified by this plan.
**Performance Goals**: Error formatting is off the hot path. The custom formatter runs once per failed GraphQL operation; target negligible overhead (<1ms p99 per error entry, dominated by `model_dump()`).
**Constraints**:
- Apollo Client compatibility — `extensions.code`/`extensions.data` are standard GraphQL extensions; no exotic link middleware required.
- Backward-compatibility: GraphQL `message`/`locations`/`path` preserved on every error (FR-002). The breaking change to `extensions.code` (int→string) is scoped to GraphQL only; REST `/api/...` bodies unchanged.
- Same-release coupling: backend formatter + frontend Apollo migration + frontend binding regeneration must land in one release (or the auth path breaks).
- No backward-compat shim (see research.md decision R-007).
**Scale/Scope**:
- 9 catalogued codes for v1.
- ~6 backend exception classes adopted (`NodeNotFoundError`, `AuthorizationError` split into 2 codes, `PermissionDeniedError`, `ValidationError` split into 3 codes, `BranchNotFoundError`, `SchemaNotFoundError`).
- 2 frontend call sites migrated (`graphqlClientApollo.tsx:66`, `pages/login.tsx:27-29`).
- 1 new package directory `backend/infrahub/errors/`.
- 1 generated TypeScript file at `frontend/app/src/shared/api/errors/catalogue.generated.ts`.
- 1 new docs page generated from the catalogue.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ N/A | No node/attribute/relationship schema changes. Catalogue is a typed registry, not data schema. |
| II. Branch-Safe by Default | ✅ N/A | Error formatting is branch-agnostic; no Cypher queries added or modified. |
| III. Type Safety & Explicit Contracts | ✅ PASS | `data` payloads are Pydantic models per FR-004; bindings are generated TypeScript; GraphQL extension shape is documented in `contracts/graphql-error-envelope.md`; catalogue schema in `contracts/catalogue-schema.md`. No untyped dicts cross the formatter boundary. |
| IV. Test Discipline | ✅ PASS | Unit (catalogue + formatter), functional (end-to-end GraphQL response shape for every code), E2E (US2 multi-field form, US2 permission routing). All catalogue codes covered by SC-001 / SC-008 integration tests. SC-005 sync-break test added to CI. |
| V. Query Performance & Efficiency | ✅ N/A | No new Cypher queries. Formatter overhead negligible. |
| VI. Security & Input Boundaries | ✅ PASS | FR-013 covered — `data` payload models exclude permission-restricted fields by construction. No new user input is interpolated into the formatter; the `data` object is built from typed exception attributes. Error messages still pass through existing sanitization. |
| VII. Simplicity & Maintainability | ✅ PASS | No new abstractions invented: reuse Pydantic for payloads, reuse `json-schema-to-typescript` for codegen, reuse existing Invoke tasks pattern, reuse existing Docusaurus docs pipeline. No backward-compat shim. Catalogue covers 9 codes (not "all errors") per FR-005 "right and useful over many". |

**Result**: No violations. Complexity Tracking section is unused.

### Frontend principles (US2 ships UI changes)

| Principle | Status | Notes |
|---|---|---|
| Reuse Before Reinvent | ✅ PASS | No new UI primitives — feed existing form-field error display from the new typed errors; route permission errors through the existing dialog system. |
| Single State Owner | ✅ PASS | Form state stays in `useForm` (frontend pattern). Apollo holds the GraphQL response; errors flow through the existing error link, not duplicated into local state. |
| Backend Authoritative | ✅ PASS | All `code` and `data` shapes come from the generated bindings; no frontend-side enum of expected codes. |
| Component Contracts Designed for All Callers | ✅ PASS | No shared components touched (only consumer wiring). |
| E2E Happy Path | ✅ PASS | New Playwright test for US2 multi-field form + permission routing path (SC-004). |

### Shared Components Inventory

| Need | Reusing | Source |
|---|---|---|
| Form-field error display | existing form field-error UI | `frontend/app/src/shared/components/form/...` |
| Apollo error link | existing `errorLink` | `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx` |
| Permission dialog | existing permission/toast routing | wherever `pages/login.tsx:27-29` currently dispatches |

No "(building new)" rows — no Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/infp-468-graphql-error-catalogue/
├── spec.md                # Feature specification (existing)
├── discovery.md           # Discovery analysis (existing)
├── checklists/
│   └── requirements.md    # Spec quality checklist (existing)
├── plan.md                # This file
├── research.md            # Phase 0 — design decisions
├── data-model.md          # Phase 1 — catalogue entities + payload shapes
├── contracts/             # Phase 1 — wire-format and schema contracts
│   ├── graphql-error-envelope.md
│   ├── catalogue-schema.md
│   └── catalogue.example.json
├── quickstart.md          # Phase 1 — how to add/consume catalogue codes
└── tasks.md               # Phase 2 — generated by /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── errors/                              # NEW package
│   │   ├── __init__.py
│   │   ├── catalogue.py                     # Registry of code → (PayloadModel, description, stability)
│   │   ├── payloads.py                      # Pydantic models for each code's data payload
│   │   ├── exceptions.py                    # Catalogue-aware exception base + per-code raisers (or re-exports of existing classes with .code attribute)
│   │   └── export.py                        # Render catalogue → JSON Schema file
│   ├── exceptions.py                        # Existing — annotate adopted classes with their catalogue code
│   ├── api/
│   │   └── exception_handlers.py            # Modified — branch on request.url.path to emit GraphQL-shaped error for /graphql route
│   ├── graphql/
│   │   ├── app.py                           # Existing — accepts error_formatter; we install ours at construction
│   │   ├── initialization.py                # Modified — wire catalogue_error_formatter into InfrahubGraphQLApp(error_formatter=...)
│   │   └── error_formatter.py               # NEW — graphql-core format_error wrapper that populates extensions.{code,http_status,data}
│   └── log_forwarding/                      # Existing — pass catalogue code through structured logs (FR-018)
└── tests/
    ├── unit/errors/                         # NEW — catalogue registry, payload model unit tests
    ├── unit/graphql/                        # error_formatter unit tests
    └── functional/graphql/                  # NEW or extend — end-to-end response-shape tests for each code

frontend/
└── app/
    ├── src/
    │   ├── shared/
    │   │   └── api/
    │   │       └── errors/                  # NEW directory
    │   │           ├── catalogue.generated.ts   # Generated TS types from catalogue.json
    │   │           └── index.ts                 # Hand-written re-exports + typed-fallback union
    │   └── shared/api/graphql/graphqlClientApollo.tsx   # Modified — switch on string code
    └── tests/
        └── e2e/
            └── error-catalogue.spec.ts      # NEW — US2 multi-field form + permission routing

tasks/
├── backend.py                               # Existing — add `export-error-catalogue` task
├── frontend.py                              # NEW — host `regenerate-error-bindings` and `check-error-bindings` Invoke tasks
└── docs.py                                  # Existing — add catalogue docs render step

docs/
└── docs/
    └── reference/error-catalogue/           # NEW — generated docs page (FR-010, FR-012)
        └── index.md

schema/                                       # Existing — committed build artefacts
└── error-catalogue.json                      # NEW — committed machine-readable schema (FR-006, FR-012)

changelog/
└── +graphql-error-catalogue.changed.md       # NEW — towncrier fragment (changed section per pyproject.toml), calls out the breaking change
```

**Structure Decision**: Web application (Option 2). The backend gets a new `backend/infrahub/errors/` package; the frontend gets a generated bindings file under the existing `shared/api/` convention; tooling is added as Invoke tasks alongside existing ones. The Python SDK lives in the `python_sdk/` submodule and is out of scope for this repo's changes — its bindings are generated and tested in the SDK repository, consuming `schema/error-catalogue.json` as the cross-repo contract.

## Complexity Tracking

No constitutional violations. No complexity entries to justify.
