# Data Model: Frontend Request Prioritization (`X-Priority`)

**Feature**: IFC-2890 | **Date**: 2026-07-14

This feature introduces no persisted data. The "data model" is the typed contract for the emittable priority value and the surfaces that carry it.

## Entities

### `RequestPriority` (new, frontend)

The typed contract for the priority the frontend may emit.

| Field / member | Type | Notes |
|----------------|------|-------|
| `RequestPriority` | `'high' \| 'low'` | The only two values the frontend may emit. `'normal'` is deliberately excluded — the backend's fallback, never something the frontend sends. |
| `DEFAULT_PRIORITY` | `RequestPriority` (`'high'`) | Applied unconditionally at every transport when no opt-in is present. |
| `PRIORITY_HEADER` | `string` (`'X-Priority'`) | Outbound header name. Sent title-cased; the backend matches case-insensitively (`x-priority`). |

**Validation rules**:
- The value written to the header MUST be exactly `'high'` or `'low'`.
- No frontend-origin request MUST be emitted without the header (no unheadered path) — FR-003.
- The header MUST NOT be attached to requests whose target host is not the Infrahub API — FR-007.

**State**: none — the value is derived per-request from the opt-in (or the default), not stored.

### `X-Priority` header (existing, backend-parsed)

Unchanged by this feature except as an emitter. The backend (`backend/infrahub/api/admission/priority.py`) parses it into `high`/`normal`/`low`, case-insensitive; missing/invalid → `normal` (`was_explicit=False`, increments `infrahub_admission_missing_priority_total`).

### CORS allowed-headers list (existing, backend config)

`backend/infrahub/config.py :: default_cors_allow_headers()` — extended by exactly one value, `"x-priority"`, so cross-origin preflight permits the header.

## Opt-in surfaces (one convention, per transport)

| Transport | Default source | `low` opt-in surface | Consumed by |
|-----------|----------------|----------------------|-------------|
| GraphQL (Apollo) | priority link default | Apollo operation `context: { priority: 'low' }` | new `setContext` priority link in `graphqlClientApollo.tsx` |
| REST (`openapi-fetch`) | middleware default | per-request option `{ priority: 'low' }` | `authMiddleware.onRequest` in `rest/client.ts` |
| Raw fetch (`fetchUrl`) | argument default | optional arg `{ priority: 'low' }` | `fetchUrl` in `rest/fetch.ts` |
| GraphiQL fetcher | hard-coded `high` | none (sandbox tool; always `high`) | `use-graphiql-fetcher.ts` |

## Transport injection matrix (requirement traceability)

| Transport | Emits default `high` | Honors `low` opt-in | Survives 401 replay | Survives upload | External-host guard |
|-----------|:--:|:--:|:--:|:--:|:--:|
| Apollo GraphQL | FR-001 | FR-002 | FR-004 | FR-004 (shared upload link) | n/a (Infrahub only) |
| REST `openapi-fetch` | FR-001 | FR-002 | FR-004 (clone) | n/a | n/a (baseUrl only) |
| Raw fetch `fetchUrl` | FR-001 | FR-002 | n/a | n/a | FR-007 |
| GraphiQL fetcher | FR-001/FR-003 | n/a | n/a | n/a | n/a |

## Query-class classification (FR-005 / SC-002)

| Class | Priority | Mechanism |
|-------|----------|-----------|
| Interactive (page loads, mutations, ~89 call sites) | `high` | inherit default — no change |
| Watched live-status polls (task list/status, PC details/events, branch action state) | `high` | inherit default — explicitly asserted, never declared `low` |
| Background / preload | `low` | single opt-in at definition — **empty set in v1** |
