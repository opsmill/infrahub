# Request Priority (`X-Priority`)

The frontend is a first-class emitter of the `X-Priority` request header so the backend
admission layer (IFC-2886) can serve interactive users first and shed background frontend
work first under overload.

Contract module: `frontend/app/src/shared/api/priority/index.ts`. Spec:
`specs/ifc-2890-frontend-request-priority/`.

## The contract

- `type RequestPriority = 'high' | 'low'` — the only two values the frontend may emit.
  `'medium'` is the backend's fallback and is deliberately unrepresentable here.
- `DEFAULT_PRIORITY = 'high'` — every transport applies this unconditionally, so no
  frontend-origin request is ever emitted `medium` or unheadered.
- `PRIORITY_HEADER = 'X-Priority'`.
- `resolvePriority(value)` — normalizes an untyped per-request value: returns `'low'`
  only for exactly `'low'`, everything else (`'medium'`, `undefined`, garbage) → `'high'`.
  Each transport runs its value through this before writing the header, so a stray or
  legacy value cannot leak an out-of-contract priority.

## Four injection points (default `high`)

The header is stamped at each transport entry, not at call sites:

1. **Apollo GraphQL** — `priorityLink` (`setContext`) in
   `shared/api/graphql/graphqlClientApollo.tsx`, inserted into the link chain. Uploads
   ride the same terminating `createUploadLink`, so they inherit it for free.
2. **REST (`openapi-fetch`)** — `authMiddleware.onRequest` in `shared/api/rest/client.ts`.
   The header is set before the `Request` clone captured for 401 replay, so replay
   preserves it.
3. **Raw fetch** — `fetchUrl` in `shared/api/rest/fetch.ts`, **origin-guarded**: the
   header is stamped only when the URL's origin matches the Infrahub API server, so it
   never leaks to a non-Infrahub host (FR-007).
4. **GraphiQL fetcher** — `shared/libs/graphiql/use-graphiql-fetcher.ts` sets
   `X-Priority: high` on its raw sandbox fetch.

The header survives both 401-refresh replay paths (Apollo `...oldHeaders` spread; REST
stored clone) and the file-upload rebuild path.

## Opting a request down to `low` (one convention per transport)

The default is `high`; an undeclared request needs no change. To demote a single request,
declare it at the call site using its transport's idiom:

- **GraphQL** — `context: { priority: 'low' }` on the operation.
- **REST** — pre-set the header via `params: { header: { 'X-Priority': 'low' } }`
  (openapi-fetch's `options` is read-only and exposes no custom field, so the header
  itself is the opt-in surface).
- **Raw fetch** — the `{ priority: 'low' }` option argument to `fetchUrl`.

No helper wraps these: the v1 `low` set is empty (no production caller demotes yet), so a
helper would serve only tests (YAGNI). The mechanism plus convention is the deliverable.

## Watched status stays `high`

Watched live-status polls (task list/status, proposed-change details/events, branch action
state) are left **undeclared**, so they inherit the `high` default even though they poll on
an interval — they carry data a user is actively watching and must not be shed. Tests assert
their `high`-ness explicitly and that none is declared `low` (FR-005).

## Backend note (CORS)

Two additive backend changes let cross-origin frontends (dev/split-host) send the header:

- `backend/infrahub/config.py` adds `x-priority` to the `default_cors_allow_headers()`
  default, so the CORS preflight allow-lists it.
- `backend/infrahub/api/admission/middleware.py` exempts CORS `OPTIONS` preflight from
  admission. A preflight never carries a custom header, so without the exemption it would
  arrive as `medium` and could be shed under load — breaking cross-origin requests exactly
  when the feature matters.
