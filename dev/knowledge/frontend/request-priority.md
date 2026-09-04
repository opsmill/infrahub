# Request Priority (`X-Priority`)

The frontend is a first-class emitter of the `X-Priority` request header so the backend
admission layer (IFC-2886) can serve interactive users first and shed background frontend
work first under overload.

Contract module: `frontend/app/src/shared/api/priority/index.ts`. Spec:
`dev/specs/archive/ifc-2890-frontend-request-priority/`. The server side that consumes this header
is documented in [API Backpressure](../backend/api-backpressure.md).

Why the client declares priority at all (rather than the server inferring it), why the claim is
trusted, and why the header is stamped at the transport boundary instead of at call sites:
[ADR 0008](../../adr/0008-client-declared-request-priority.md).

## The contract

- `type RequestPriority = 'high' | 'low'` — the only two values the frontend may emit.
  `'medium'` is the backend's fallback and is deliberately unrepresentable here.
- `DEFAULT_PRIORITY = 'high'` — every transport applies this unconditionally, so no
  frontend-origin request is ever emitted `medium` or unheadered.
- `PRIORITY_HEADER = 'X-Priority'`.
- `resolvePriority(value)` — normalizes an untyped per-request value: returns `'low'`
  only for exactly `'low'`, everything else (`'medium'`, `undefined`, garbage) → `'high'`.
  Any transport that accepts a per-request priority runs its value through this before
  writing the header, so a stray or legacy value cannot leak an out-of-contract priority.
  A transport that only ever emits the default writes `DEFAULT_PRIORITY` directly.

## Four injection points (default `high`)

The header is stamped at each transport entry, not at call sites:

1. **GraphQL (urql)** — the `fetchOptions` handed to each `Client` in
   `shared/api/graphql/client.ts`, so every operation on that client carries it. Uploads ride
   the same terminating `fetchExchange`, so they inherit it for free.
2. **REST (`openapi-fetch`)** — `authMiddleware.onRequest` in `shared/api/rest/client.ts`.
   The header is set before the `Request` clone captured for 401 replay, so replay
   preserves it.
3. **Raw fetch** — `fetchUrl` in `shared/api/rest/fetch.ts`, **origin-guarded**: the
   header is stamped only when the URL's origin matches the Infrahub API server, so it
   never leaks to a non-Infrahub host (FR-007).
4. **GraphiQL fetcher** — `shared/libs/graphiql/use-graphiql-fetcher.ts` sets
   `X-Priority: high` on its raw sandbox fetch.

The header survives both 401-refresh replay paths (urql's `authExchange` replays the operation
with its context, including `fetchOptions`; REST replays a stored clone) and the file-upload
rebuild path.

## Opting a request down to `low` (one convention per transport)

The default is `high`; an undeclared request needs no change. To demote a single request,
declare it at the call site using its transport's idiom:

- **REST** — pre-set the header via `params: { header: { 'X-Priority': 'low' } }`
  (openapi-fetch's `options` is read-only and exposes no custom field, so the header
  itself is the opt-in surface).
- **GraphQL** has no per-operation opt-down.

## Watched status stays `high`

Watched live-status polls (task list/status, proposed-change details/events, branch action
state) are left **undeclared**, so they inherit the `high` default even though they poll on
an interval — they carry data a user is actively watching and must not be shed. Tests assert
their `high`-ness explicitly and that none is declared `low` (FR-005).

## What happens when a request is shed

A shed request is answered `429 Too Many Requests` with a `Retry-After` hint
([ADR 0007](../../adr/0007-adaptive-retry-after-under-load.md)). The frontend honours it in the
transport, not in the query cache: `retryingFetch` (`shared/api/rate-limit/retrying-fetch.ts`)
wraps `fetch` for all four injection points above, so a shed request is replayed below the auth
layer and below TanStack Query — which keeps `retry: false`, because a 429 is the only status
worth replaying and only the transport can still read the header.

The policy lives in `shared/api/rate-limit/policy.ts`, the browser counterpart of the SDK's
`infrahub_sdk/rate_limit.py`: at most 3 retries inside a 15s window. An advised wait is a floor,
never a ceiling — jitter is added on top, so the page-load burst of shed requests de-synchronises
and no retry lands before the server said it could. A wait that would run past the window ends the
retries instead, because a person is waiting on the response. With no advice, the delay is a
full-jitter exponential backoff from 300ms.

`GET`/`HEAD`/`OPTIONS` is always replayable. Anything else is replayed only when the body carries
Infrahub's shed envelope (`{"errors": [{"extensions": {"code": 429}}]}`), which is what proves the
admission layer answered before the handler ran. A 429 from an ingress or CDN in front of the API
carries no such guarantee, so a mutation is not replayed against one.

Once the retries are spent, the 429 surfaces as an ordinary error. On the GraphQL side it is
recognised before the error catalogue (`shared/api/rate-limit/shed-envelope.ts`): the shed
envelope's `code` is an integer HTTP status rather than a catalogue identifier, so without that
branch it collapses into `UNDEFINED_ERROR` and asks a developer to register a code that must never
be registered.

## Backend note (CORS)

Two additive backend changes let cross-origin frontends (dev/split-host) send the header:

- `backend/infrahub/config.py` adds `x-priority` to the `default_cors_allow_headers()`
  default, so the CORS preflight allow-lists it.
- `backend/infrahub/api/admission/middleware.py` exempts CORS `OPTIONS` preflight from
  admission. A preflight never carries a custom header, so without the exemption it would
  arrive as `medium` and could be shed under load — breaking cross-origin requests exactly
  when the feature matters.
