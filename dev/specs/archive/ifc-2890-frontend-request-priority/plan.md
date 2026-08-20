# Implementation Plan: Frontend Request Prioritization (`X-Priority`)

**Branch**: `dga/feat-priority-frontend-nl5ss` | **Date**: 2026-07-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/ifc-2890-frontend-request-priority/spec.md`

## Summary

Make the Infrahub frontend a first-class emitter of the `X-Priority` request header (values `high`/`low` only) so the backend admission layer (IFC-2886) can serve interactive users first and shed background frontend work first under overload. Every frontend-originated request gets `X-Priority: high` by default via header injection at each transport entry point; a single per-query opt-in demotes a query to `low`. One additive backend change adds `x-priority` to the CORS allowed-headers default so cross-origin frontends can send it. No new endpoints, no GraphQL schema change, no persistence.

Technical approach: a new `RequestPriority` type module (typed `'high' | 'low'` union, default `high`, header-name constant) is consumed by injection points in each of the frontend transports — the Apollo link chain, the `openapi-fetch` REST middleware, the raw-fetch helper, and the GraphiQL fetcher. Both 401-refresh replay paths and the file-upload path already spread/preserve request headers, so the header survives them once injected at the right layer. Watched live-status polls remain `high` (they are undeclared, so they inherit the default). The `low` opt-in is a single unified developer-facing convention: a GraphQL Apollo `context` field and a REST/fetch per-request option, both reading the same `RequestPriority` value.

## Technical Context

**Language/Version**: TypeScript 5.9 (frontend), Python 3.14 (backend CORS change only)

**Primary Dependencies**: React 19.2 + Apollo Client 3.13 (`@apollo/client`), `apollo-upload-client` 18 (`createUploadLink`), `openapi-fetch` 0.17 (REST), TanStack Query 5 (polling/refetch), Vitest 4.1 (unit); backend: FastAPI 0.131 `CORSMiddleware`, Pydantic settings

**Storage**: N/A (no persistence; a request header only)

**Testing**: Vitest unit tests per transport + opt-in helper; backend component/contract test for the CORS preflight; existing Playwright E2E for the interactive-vs-background scenario

**Target Platform**: Browser (frontend) talking to the Infrahub FastAPI server; same-origin in prod, cross-origin in dev/split-host

**Project Type**: Web application (React frontend + FastAPI backend)

**Performance Goals**: No added latency; header injection is O(1) per request. Joint outcome (SC-004): interactive requests hold bounded latency / ~0 shed under saturating background load once the backend admission layer is live

**Constraints**: The only two emittable values are `high` and `low` (never `normal`/unheadered) for frontend-origin requests; the header MUST NOT leak to non-Infrahub hosts; the header MUST survive 401-refresh replay and file-upload rebuild paths

**Scale/Scope**: 4 transport injection points, 1 new type module + opt-in helper, 1 backend CORS one-liner, ~89 interactive call sites (all unchanged — they inherit the default). Initial `low` set is empty (no prefetch/preload exists today)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Relevance | Status |
|-----------|-----------|--------|
| **III — Type Safety & Explicit Contracts** | `RequestPriority` is a `'high' \| 'low'` union with a named default and a header-name constant; no stringly-typed values, no `any`. The opt-in helper is typed. | ✅ Pass |
| **IV — Test Discipline** | Every FR has a one-line verification. Unit tests per transport (default `high`, opt-down `low`, replay/upload preservation), a backend contract test for the CORS preflight, and an E2E scenario asserting interactive `high` vs background `low` and no `normal`. Tests mirror source (`shared/api/**`). | ✅ Pass |
| **VII — Simplicity & Maintainability** | One automatic default + one opt-in, not a per-call priority taxonomy. The shared `RequestPriority` module serves ≥4 callers (the transports), satisfying the "≥2 callers before extraction" rule. No new dependency. | ✅ Pass |
| **VI — Security & Input Boundaries** | Header is additive and non-secret; it MUST NOT be sent to non-Infrahub hosts (FR-007). The CORS change is security-adjacent and additive (one allowed-header value), flagged for review per AGENTS.md "Ask First." No auth/authz change. | ✅ Pass (gate acknowledged) |
| **I — Schema-Driven Integrity** | No schema change; no generated files touched. | ✅ N/A |
| **II — Branch-Safe by Default** | No database access; no branch/temporal concern. | ✅ N/A |
| **V — Query Performance & Efficiency** | No new DB queries. | ✅ N/A |

**Governance gate acknowledged**: adding `x-priority` to the CORS allowed-headers default is a security-adjacent config change ("Ask First"). It is additive, introduces no new endpoint or contract, and ships with the frontend change. No unjustified violations → **Complexity Tracking not required**.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2890-frontend-request-priority/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (transport + CORS contracts)
│   ├── request-priority.contract.md
│   └── cors-preflight.contract.md
├── checklists/
│   └── requirements.md  # from /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
frontend/app/src/shared/api/
├── priority/                              # NEW — the RequestPriority contract
│   ├── index.ts                           #   RequestPriority type, DEFAULT_PRIORITY, PRIORITY_HEADER, opt-in helpers
│   └── index.test.ts                      #   unit tests for the helper + constants
├── graphql/
│   ├── graphqlClientApollo.tsx            # EDIT — add priority setContext link to from([...]) chain
│   └── graphqlClientApollo.test.ts        # EDIT/ADD — assert high default, low via context, survives 401 replay
├── rest/
│   ├── client.ts                          # EDIT — authMiddleware.onRequest sets X-Priority; reads per-request opt-in
│   ├── client.test.ts                     # NEW — assert high default, low opt-in, survives 401 clone-replay
│   ├── fetch.ts                           # EDIT — fetchUrl sets X-Priority (Infrahub host only), optional priority arg
│   └── fetch.test.ts                      # NEW — assert high default, low arg, no header to external host
└── ...
frontend/app/src/shared/libs/graphiql/
└── use-graphiql-fetcher.ts                # EDIT — GraphiQL raw fetch sets X-Priority: high

backend/infrahub/
└── config.py                              # EDIT — default_cors_allow_headers() += "x-priority" (line ~50-51)
backend/tests/                             # ADD — component test: OPTIONS preflight allow-lists x-priority
```

**Structure Decision**: Web application. Frontend changes are concentrated under `frontend/app/src/shared/api/` (the transport layer) plus one GraphiQL fetcher, following the existing Feature-Sliced `shared/api/**` layout. The single new module `shared/api/priority/` holds the typed contract consumed by all transports. The backend change is a one-line addition to the CORS allowed-headers default in `backend/infrahub/config.py`, with a component test. Watched-status query definitions are **not** edited — they inherit the `high` default; only their `high`-ness is asserted in tests.

## Phase 0 — Research

See [research.md](./research.md). All PRD open questions resolved:

1. **`low` opt-in shape** → a single unified convention: GraphQL via Apollo operation `context: { priority: 'low' }` consumed by a dedicated priority link; REST/raw-fetch via a per-request `priority` option/argument consumed by the middleware/helper. Both read the same `RequestPriority` value from `shared/api/priority`.
2. **Initial `low` set** → empty in v1. The codebase has no `prefetchQuery`/`ensureQueryData`/hover-prefetch/Apollo-prefetch. The mechanism + convention is the deliverable; the two `refetchIntervalInBackground: true` polls (branch action state, proposed-change details) are **watched** status and must stay `high`, so they are explicitly not demoted.

## Phase 1 — Design & Contracts

- **Data model**: [data-model.md](./data-model.md) — `RequestPriority` union, `DEFAULT_PRIORITY`, `PRIORITY_HEADER`, opt-in surfaces, transport injection matrix.
- **Contracts**: [contracts/request-priority.contract.md](./contracts/request-priority.contract.md) (outbound header contract per transport + query class) and [contracts/cors-preflight.contract.md](./contracts/cors-preflight.contract.md) (backend CORS allow-header contract).
- **Quickstart**: [quickstart.md](./quickstart.md) — runnable validation of the header on each transport, the CORS preflight, and the E2E interactive-vs-background scenario.
- **Agent context**: CLAUDE.md SPECKIT markers updated to point at this plan.

### Design decisions

1. **Injection layer per transport (default `high`)**
   - **GraphQL**: add a `setContext` "priority link" to `from([errorLink, authLink, priorityLink, httpLink])` (or fold into `authLink`) that sets `headers['X-Priority'] = context.priority ?? DEFAULT_PRIORITY`. Because uploads ride the same `createUploadLink` terminating link, uploads are covered for free (FR-004 upload half).
   - **REST**: in `authMiddleware.onRequest` (`rest/client.ts`), `request.headers.set('X-Priority', options.priority ?? DEFAULT_PRIORITY)`. The `Request` clone captured for 401 replay is taken after headers are set, so the header survives replay (FR-004 replay half).
   - **Raw fetch**: in `fetchUrl` (`rest/fetch.ts`), set the header only for Infrahub-host URLs; accept an optional `priority` arg. Guard against external hosts (FR-007).
   - **GraphiQL fetcher**: set `X-Priority: high` in `use-graphiql-fetcher.ts` (the fourth raw transport) so no frontend request is unheadered (FR-003).

2. **The `low` opt-in (single convention, FR-002)** — a helper in `shared/api/priority` exposing the value; GraphQL callers pass `context: { priority: 'low' }`, REST/fetch callers pass `{ priority: 'low' }`. Declared once at the query definition; all fetches for that query inherit it. Undeclared → `high`.

3. **Watched status stays `high` (FR-005)** — task list, task status, proposed-change details/events, and branch action state queries are left undeclared, so they inherit `high`. Tests assert their `high`-ness explicitly and assert none is declared `low`.

4. **No `normal`, no unheadered (FR-003)** — the only values the frontend can emit are `high` and `low`; the default is applied unconditionally at each transport, so there is no path that omits the header for a frontend-origin request.

5. **Backend CORS (FR-006)** — append `"x-priority"` to `default_cors_allow_headers()` in `backend/infrahub/config.py`. `InfrahubCORSMiddleware` reads `config.SETTINGS.api.cors_allow_headers`. The backend already parses `x-priority` case-insensitively and accepts `high`/`low`, so no parser change is needed.
   - **Preflight must not be admission-gated** (critique E2): a CORS `OPTIONS` preflight never carries custom headers, so it arrives with no `X-Priority`; `AdmissionMiddleware` is registered outermost (`server.py:221`, after CORS at `:205`) and excludes by path, not method — so a preflight would be treated as `normal` and could be shed under saturating load, breaking cross-origin requests (FR-006) exactly when the feature matters. Before implementing, **verify** that admission short-circuits/exempts `OPTIONS` preflight (or safe/non-sheddable methods); if it does not, that exemption is part of this feature. Record the finding either way.
   - **Test level** (critique E5): a **component test** (FastAPI `TestClient`, `OPTIONS` preflight) placed in the backend test tree mirroring `middleware.py`/`config.py`, discoverable via `-k "cors and priority"`, asserts `x-priority` appears in `Access-Control-Allow-Headers` and that the preflight is not rejected by admission.

### Constitution re-check (post-design)

No new violations introduced. The design adds one typed module + four small injection edits + one backend config line, all covered by tests. Simplicity preserved (single default + single opt-in). ✅ Gate holds.
