# Implementation Plan: Configuration Wizard with Marketplace Schema Browser

**Branch**: `atg-01-config-wizard` | **Date**: 2026-02-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/atg-01-config-wizard/spec.md`

## Summary

Build a configuration wizard that detects when no user-defined schemas exist and guides first-time users through: (1) creating Git credentials, (2) connecting a read/write repository, (3) browsing and selecting schemas from the Infrahub Marketplace, and (4) installing selected schemas via a Prefect background job that commits schema files to the repository and pushes to the remote. The backend proxies marketplace API calls through new REST endpoints using the existing `HttpxAdapter`. The frontend renders a multi-step wizard overlay with a card-based schema browser.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend)
**Primary Dependencies**: FastAPI 0.121.1, httpx (backend HTTP client), React 19.2, react-hook-form, Jotai (state), Apollo Client 3.13 (GraphQL)
**Storage**: Neo4j 5.28 (existing), Git repositories (schema files)
**Testing**: pytest 7.4 (backend), Vitest 4.0 (frontend unit), Playwright 1.56 (frontend E2E)
**Target Platform**: Web application (Docker-deployed backend, browser frontend)
**Project Type**: Web (full-stack: backend API + frontend SPA)
**Performance Goals**: Marketplace catalog loads within 3 seconds; installation completes within 60 seconds for up to 10 schemas
**Constraints**: Must work with existing Prefect workflow infrastructure; must use existing GraphQL mutations for credential/repository creation; marketplace API is external and public
**Scale/Scope**: ~50 marketplace schemas currently; wizard is session-scoped (no persistent wizard state)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Gate

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | Uses existing schema entities (CorePasswordCredential, CoreRepository). New marketplace data models are Pydantic models only, not persisted in Neo4j. No schema changes required. |
| II. Branch-Safe by Default | PASS | Schema detection uses `namespacesAtom` which is branch-aware. Repository creation already handles branching. Schema installation writes to the repository's default branch. |
| III. Type Safety & Explicit Contracts | PASS | All marketplace response data modeled with Pydantic (backend) and TypeScript interfaces (frontend). API contracts defined in `contracts/`. No `any` types. |
| IV. Test Discipline | PASS | Plan includes unit tests for marketplace client/models, component tests for wizard steps, E2E tests for full flow. |
| V. Query Performance | PASS | No new Neo4j queries. Marketplace API calls are proxied HTTP requests. Pagination supported via GraphQL relay connections. |
| VI. Security & Input Boundaries | PASS | Marketplace proxy requires authentication. External API responses validated via Pydantic models. No user input interpolated into external queries. |
| VII. Simplicity & Maintainability | PASS | Follows existing patterns (HttpxAdapter for HTTP, Prefect for workflows, entity-based frontend structure). No new dependencies required. No premature abstractions. |

### Post-Design Gate

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | No schema modifications. Marketplace models are read-only transport objects. |
| II. Branch-Safe by Default | PASS | Wizard detection reads from branch-aware schema atoms. Installation targets a specific branch. |
| III. Type Safety & Explicit Contracts | PASS | Full Pydantic models for all marketplace responses. TypeScript interfaces for all frontend data. REST contracts documented. |
| IV. Test Discipline | PASS | Test plan covers all levels: unit, component, E2E. |
| V. Query Performance | PASS | No new database queries. HTTP calls have configurable timeouts via HttpxAdapter. |
| VI. Security & Input Boundaries | PASS | Auth required on all proxy endpoints. External responses validated. Schema content validated before committing. |
| VII. Simplicity & Maintainability | PASS | Reuses existing infrastructure (HttpxAdapter, Prefect, react-hook-form, existing mutation patterns). New code follows established entity-based organization. |

## Project Structure

### Documentation (this feature)

```text
specs/atg-01-config-wizard/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research decisions
├── data-model.md        # Data model definitions
├── quickstart.md        # Architecture overview and development guide
├── contracts/           # API contracts
│   └── marketplace-proxy-api.md
├── checklists/          # Quality checklists
│   └── requirements.md
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── api/
│   │   ├── main.py                    # Modified: register marketplace router
│   │   └── marketplace.py             # New: marketplace proxy REST endpoints
│   ├── marketplace/                   # New: marketplace integration package
│   │   ├── __init__.py
│   │   ├── client.py                  # GraphQL client for marketplace API
│   │   ├── models.py                  # Pydantic response models
│   │   └── tasks.py                   # Prefect workflow for schema installation
│   └── workflows/
│       └── catalogue.py               # Modified: add MARKETPLACE_SCHEMA_INSTALL workflow
└── tests/
    └── unit/
        └── marketplace/               # New: unit tests
            ├── test_client.py
            └── test_models.py

frontend/app/
├── src/
│   ├── entities/
│   │   ├── marketplace/               # New: marketplace entity
│   │   │   ├── api/
│   │   │   │   └── marketplace.queries.ts
│   │   │   ├── ui/
│   │   │   │   ├── marketplace-schema-card.tsx
│   │   │   │   ├── marketplace-schema-card.test.tsx
│   │   │   │   ├── marketplace-browser.tsx
│   │   │   │   └── marketplace-browser.test.tsx
│   │   │   └── types.ts
│   │   └── config-wizard/             # New: config wizard entity
│   │       ├── ui/
│   │       │   ├── config-wizard.tsx
│   │       │   ├── config-wizard.test.tsx
│   │       │   ├── wizard-step-welcome.tsx
│   │       │   ├── wizard-step-credentials.tsx
│   │       │   ├── wizard-step-repository.tsx
│   │       │   ├── wizard-step-schemas.tsx
│   │       │   └── wizard-step-confirm.tsx
│   │       ├── hooks/
│   │       │   └── use-has-user-schemas.ts
│   │       └── types.ts
│   └── pages/
│       └── app-layout.tsx             # Modified: add wizard trigger
└── tests/
    └── e2e/
        └── config-wizard.spec.ts      # New: E2E test
```

**Structure Decision**: Full-stack web application following the existing entity-based frontend architecture (`entities/<feature>/api|ui|types`) and the backend's module-based organization. New backend code goes in a `marketplace/` package under `infrahub/`. New frontend code goes in two entities: `marketplace/` (reusable schema browser) and `config-wizard/` (wizard flow).

## Complexity Tracking

No constitution violations. No complexity justifications required.
