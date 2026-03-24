# Implementation Plan: Login/Logout Activity Events

**Branch**: `infp-474-login-logout-events` | **Date**: 2026-03-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/infp-474-login-logout-events/spec.md`

## Summary

Adds two new Prefect-backed activity events (`infrahub.account.logged_in`, `infrahub.account.logged_out`) to the existing Infrahub event system. Events are emitted from the three authentication endpoints (password, OAuth2, OIDC) and the logout endpoint. A new `AuthResult` dataclass carries rich account metadata (name, type, groups, roles, session ID) from the auth functions to the endpoints, where it is combined with HTTP context (client IP, user agent) before emission. All events are fire-and-forget — failures are logged but never block authentication.

## Technical Context

**Language/Version**: Python 3.12, FastAPI 0.121.1
**Primary Dependencies**: Prefect Events (existing), RabbitMQ via `InfrahubEventService` (existing), Pydantic 2.10
**Storage**: Prefect event store (existing — no Neo4j schema changes)
**Testing**: pytest 9.0 — unit tests (`tests/unit/event/`) and component tests (`tests/component/api/`)
**Target Platform**: Linux server (Infrahub backend)
**Performance Goals**: Event emission under 5 seconds of auth action (SC-001); fire-and-forget so latency impact is negligible
**Constraints**: Event emission failure MUST NOT block authentication (FR-001/003). `infrahub.account.*` events are admin-only; query access is restricted at the GraphQL resolver layer (FR-005).
**Scale/Scope**: Backend only — no frontend changes, no DB schema changes, no SDK changes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Schema-Driven Integrity** | ✅ PASS | Auth events use Prefect storage — no Neo4j schema changes. No generated files touched. |
| **II. Branch-Safe by Default** | ✅ PASS | Auth events use default branch context; they are not branch-scoped data. |
| **III. Type Safety** | ✅ PASS | `AuthResult` is a frozen dataclass. All event fields have explicit types. `str \| None` pattern used. |
| **IV. Test Discipline** | ✅ PASS | Unit tests for event models; component tests verifying emission from API endpoints. |
| **V. Query Performance** | ✅ N/A | No new DB queries on the hot path; `_fetch_account_groups_and_roles` is a one-time lookup at login, with try/except fallback returning empty lists on failure. |
| **VI. Security** | ✅ PASS | `client_ip` and `user_agent` stored as-is, never interpolated into queries. Event emission failures logged but never surface internal details in HTTP responses. |
| **VII. Simplicity** | ✅ PASS | `AuthResult` serves all three SSO + password callers. No new abstractions beyond what's required. Fire-and-forget pattern matches existing event emission. |

## Project Structure

### Documentation (this feature)

```text
specs/infp-474-login-logout-events/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── graphql-types.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (backend only)

```text
backend/
├── infrahub/
│   ├── auth.py                          # + AuthResult, AuthenticationError, _fetch_account_groups_and_roles
│   ├── events/
│   │   ├── __init__.py                  # + export 2 new event classes
│   │   └── auth_action.py               # NEW: AccountLoggedInEvent, AccountLoggedOutEvent
│   ├── api/
│   │   ├── auth.py                      # + event emission (login success, login failure, logout)
│   │   ├── oauth2.py                    # + event emission (SSO login)
│   │   └── oidc.py                      # + event emission (SSO login)
│   ├── core/
│   │   └── constants/__init__.py        # + 2 EventType enum values
│   └── graphql/
│       └── types/
│           └── event.py                 # + 2 new ObjectType classes + EVENT_TYPES entries + admin role check
└── tests/
    ├── unit/
    │   └── event/
    │       └── test_auth_action.py      # NEW: 10 unit tests for event models
    └── component/
        └── api/
            └── test_auth_events.py      # NEW: 4 component tests for event emission
changelog/
└── +infp-474.added.md                   # NEW: changelog fragment
```

**Structure Decision**: Backend-only, single project. No frontend changes needed — auth events surface via existing GraphQL event feed query interface without new UI work.

## Complexity Tracking

No constitution violations.
