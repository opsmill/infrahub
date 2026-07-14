# Research: Frontend Request Prioritization (`X-Priority`)

**Feature**: IFC-2890 | **Date**: 2026-07-14

This document resolves the two PRD open questions and records the grounding findings from the current codebase that the design depends on. All file references are repo-relative to `frontend/app/` or `backend/` as noted.

## Open question 1 — Exact shape of the `low` opt-in

**Decision**: A single unified developer-facing convention, one per transport, all reading the same `RequestPriority` value from a new `shared/api/priority` module:

- **GraphQL**: opt in via the Apollo operation `context` — `context: { priority: 'low' }`. A dedicated `setContext` "priority link" reads `context.priority ?? DEFAULT_PRIORITY` and writes the `X-Priority` header.
- **REST (`openapi-fetch`)**: opt in via a per-request option — `apiClient.GET(path, { priority: 'low', ... })`. The registered request middleware reads the option and writes the header.
- **Raw fetch (`fetchUrl`)**: opt in via an optional `priority` argument — `fetchUrl(url, payload, { priority: 'low' })`.

**Rationale**: These are the idiomatic per-request extension points each transport already exposes (Apollo `context`, openapi-fetch request options, a helper argument). Unifying them under one exported `RequestPriority` type + helper keeps a single convention ("declare `low` once at the query definition; all fetches inherit it") without inventing a bespoke registry. Satisfies Constitution VII (one default + one opt-in) and III (typed union).

**Alternatives considered**:
- *A global registry mapping operation names → priority.* Rejected: indirection, must be kept in sync with query definitions, and easy to drift; violates YAGNI.
- *Per-call-site header setting.* Rejected: the PRD explicitly wants zero changes at the ~89 interactive call sites and a single opt-in at the definition.
- *A React context / provider.* Rejected: request priority is a property of the request, not the component tree; polls and background loads originate outside render.

## Open question 2 — Is the initial `low` set empty in v1?

**Decision**: **Empty in v1.** Ship the mechanism + convention; demote nothing by default.

**Rationale**: A thorough search found **no** prefetch/preload machinery in the frontend — no TanStack `prefetchQuery`/`ensureQueryData`, no hover-prefetch, no Apollo prefetch. The only "background-shaped" traffic is two polls with `refetchIntervalInBackground: true` (branch action state, proposed-change details), and both are **watched** live-status data that the PRD explicitly requires to stay `high` (FR-005). Therefore there is no legitimate `low` candidate today. Demoting a watched poll would make its data go stale under load — the exact failure the feature guards against.

**Alternatives considered**:
- *Demote the two `refetchIntervalInBackground` polls to `low`.* Rejected: they are watched status (FR-005) — must stay `high`.
- *Invent a `low` example query to exercise the path.* Rejected: no real background load exists; the `low` path is instead exercised by unit tests (a synthetic declared-`low` query) and by the E2E scenario, not by demoting real interactive traffic.

## Grounding findings (current code)

### Transports (frontend)

| # | Transport | Injection point | 401-replay behaviour | Notes |
|---|-----------|-----------------|----------------------|-------|
| 1 | Apollo GraphQL | `shared/api/graphql/graphqlClientApollo.tsx` — link chain `from([errorLink, authLink, httpLink])` (~line 231); `authLink` is a `setContext` (~lines 44-62) | `retryWithRefreshedToken` spreads `...oldHeaders` (~lines 157-185) → header survives | Terminating link is `createUploadLink` (~line 35) → **uploads ride the same chain**, covered for free |
| 2 | REST `openapi-fetch` | `shared/api/rest/client.ts` — `authMiddleware.onRequest` (~lines 26-40), registered at `apiClient.use(authMiddleware)` (~line 74) | `onResponse` replays a stored `Request` clone captured in `onRequest` (~line 37) → header set before clone survives | `requestClones` WeakMap |
| 3 | Raw fetch | `shared/api/rest/fetch.ts` — `fetchUrl()` builds headers (~lines 37-41), `fetch()` at ~line 51 | N/A | Only caller: `entities/navigation/domain/use-cases/search-docs.ts:18`. All URLs resolve to `INFRAHUB_API_SERVER_URL` |
| 4 | GraphiQL fetcher | `shared/libs/graphiql/use-graphiql-fetcher.ts` — raw `fetch()` at ~line 22, headers ~lines 24-30 | N/A | Sandbox tool; targets `CONFIG.GRAPHQL_URL(...)` (Infrahub) — must be headered to satisfy FR-003 |

**External hosts**: no `fetch()` calls to non-Infrahub hosts exist. External references (`INFRAHUB_GITHUB_URL`, `INFRAHUB_DISCORD_URL`, docs links) are anchor `href`s, not fetches. `fetchUrl` still guards on host to satisfy FR-007 defensively. `INFRAHUB_API_SERVER_URL` = `http://localhost:8000` (dev) or `window.location.origin` (prod) — `shared/config/config.ts:4-6`.

### Watched live-status queries (must stay `high`, FR-005)

| Watched data | `refetchInterval` site | Query definition |
|--------------|------------------------|------------------|
| Branch action state | `entities/branches/ui/queries/get-branch-action-state.query.ts:23-24` (5s, `refetchIntervalInBackground`) | same file → `.../api/get-branch-action-state-from-api.ts` |
| Task status (running indicator) | `entities/tasks/ui/task-status.tsx:23` (10s) | `entities/tasks/ui/queries/is-task-running-on-branch.query.ts` |
| Task display / list | `entities/tasks/ui/task-display.tsx:90` (5s) | `entities/tasks/ui/queries/get-task-list.query.ts` (+ `get-task-count`, `get-task-details`, `get-tasks-homepage`, `check-task-details`) |
| Proposed-change events | `entities/proposed-changes/ui/proposed-change-events.tsx:22` (10s) | `entities/events/ui/queries/get-events.query.ts` |
| Proposed-change details | `entities/proposed-changes/ui/proposed-change-details.tsx:49-50` (10s, `refetchIntervalInBackground`) | `entities/proposed-changes/ui/queries/get-proposed-change-details.query.ts` |

All inherit `high` (undeclared). No edits needed; tests assert `high`.

### Backend

- **CORS default**: `backend/infrahub/config.py` — `default_cors_allow_headers()` (~lines 50-51) returns `["accept", "authorization", "content-type", "user-agent", "x-csrftoken", "x-requested-with"]`. `ApiSettings.cors_allow_headers` (~lines 540-542, env `INFRAHUB_API_CORS_ALLOW_HEADERS`). Consumed by `InfrahubCORSMiddleware` (`backend/infrahub/middleware.py:10-16`), registered in `backend/infrahub/server.py:205`. **Change**: append `"x-priority"` to the default list.
- **`X-Priority` parsing (IFC-2886, already shipped)**: `backend/infrahub/api/admission/priority.py` — `parse_priority()` is case-insensitive, accepts `high`/`normal`/`low`; missing/invalid → `NORMAL` with `was_explicit=False`. Header matched lowercase as `b"x-priority"` in `backend/infrahub/api/admission/middleware.py:29`. HTTP header case-insensitivity means the frontend may send `X-Priority`. No parser change required.
- **No/invalid-priority metric**: `backend/infrahub/api/admission/metrics.py:59-62` — `infrahub_admission_missing_priority_total` Counter, incremented when `not was_explicit`. Excluded paths: `/health`, `/metrics`, `/assets`, `/favicons`, `/docs`, `/api/schema` (`middleware.py:20-27`). SC-001 is validated by this counter staying ~0 for frontend-origin traffic.

### Existing tests to mirror

- `shared/api/graphql/graphqlClientApollo.test.ts` — tests `handleGraphQLAuthError`; patterns: `makeOperation()` stub with `getContext`/`setContext`, `Observable.of(...)` for `forward`, token fixtures in `localStorage`. Mirror for the GraphQL priority test.
- `shared/api/graphql/utils.test.ts`, `shared/api/errors/index.test.ts` — sibling transport-adjacent tests.
- **No** existing test for `rest/client.ts` or `rest/fetch.ts` — new test files are greenfield in that directory.

## Summary of decisions

| Topic | Decision |
|-------|----------|
| `low` opt-in shape | Unified per-transport option reading shared `RequestPriority` (GraphQL `context`, REST option, fetch arg) |
| Initial `low` set | Empty in v1 — no real background load exists; watched polls stay `high` |
| GraphQL injection | `setContext` priority link in the `from([...])` chain (covers uploads via shared `createUploadLink`) |
| REST injection | `authMiddleware.onRequest` sets header before clone capture (survives replay) |
| Raw fetch | `fetchUrl` sets header for Infrahub host only (FR-007 guard) |
| GraphiQL | Set `high` in `use-graphiql-fetcher.ts` |
| Backend | Append `x-priority` to `default_cors_allow_headers()`; no parser change |
