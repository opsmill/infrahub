# Feature Specification: Frontend Request Prioritization (`X-Priority`)

**Feature Branch**: `dga/feat-priority-frontend-nl5ss`

**Created**: 2026-07-14

**Status**: Draft

**Ticket**: [IFC-2890](https://opsmill.atlassian.net/browse/IFC-2890) — relates to backend Story IFC-2886 (server-side admission) and JPD idea INFP-636.

**Input**: User description: "Frontend request prioritization via `X-Priority` header — the frontend declares a priority on every request it emits so the backend admission layer can serve interactive users first and shed background work first under overload."

## Overview

When an Infrahub instance runs heavy background work (generators, artifacts, diffs, syncs, computed attributes) while a human uses the frontend, both compete for the same finite API worker pool and Neo4j connections. The server-side admission layer (IFC-2886) can shed load *by priority* — but only if callers declare one via the `X-Priority` request header. Today the frontend declares nothing, so its requests arrive as `normal` and are indistinguishable from background traffic; the interactive user gets no protection from the overload the admission layer was built to handle.

This feature makes the frontend a first-class *emitter* of `X-Priority`, using only the `high`/`low` subset. Requests the user is waiting on or actively watching go out `high`; genuine background/preload work goes out `low`. `high` is the automatic default (no change at interactive call sites); `low` is a one-line opt-in declared once at a query's definition. The result: under background overload, the admission layer serves the user first and sheds background frontend work first, with no user-visible configuration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Frontend traffic wins contention under background overload (Priority: P1)

A user works in the UI while the instance is saturated with background work. Their interactive requests are emitted `high` and any background-tagged frontend requests are emitted `low`, so the admission layer admits the user's requests and sheds the background ones. The interactive experience stays responsive regardless of what else is running.

**Why this priority**: This is the reason the feature exists — protecting the interactive user under load. Delivering only this story (a `high` default on every transport) already yields a viable MVP: every frontend request is distinguishable from background traffic and wins admission.

**Independent Test**: Intercept an outbound request on each transport (GraphQL, REST, raw fetch) during a normal UI flow and assert it carries `X-Priority: high`; confirm no frontend request leaves as `normal` or unheadered.

**Acceptance Scenarios**:

1. **Given** the frontend is issuing requests, **When** a UI-blocking request (page load, mutation, or a watched live-status poll) is emitted, **Then** it carries `X-Priority: high`.
2. **Given** the frontend is issuing requests, **When** a background/preload request is emitted, **Then** it carries `X-Priority: low`.
3. **Given** any frontend-originated request, **When** it is emitted on any of the three transports, **Then** it is never emitted as `normal` or unheadered.

---

### User Story 2 - A developer marks a background load `low` (Priority: P2)

A frontend developer adds a preload/prefetch query and declares it background at its definition, using a single opt-in. All fetches for that query inherit `low`; no per-call-site changes are required. An undeclared query continues to emit `high`.

**Why this priority**: Without a low-effort opt-in, the `low` class is unusable in practice and developers would be tempted to hand-annotate call sites (error-prone, high-churn). This story makes the demotion mechanism ergonomic and is what lets background work actually shed first. It depends on Story 1's default being in place.

**Independent Test**: Define one query with the `low` opt-in and one without; assert the declared query's requests emit `X-Priority: low` and the undeclared query's requests emit `X-Priority: high`, with no other call-site changes.

**Acceptance Scenarios**:

1. **Given** a query declared background via the single opt-in, **When** it fetches, **Then** its requests emit `X-Priority: low`.
2. **Given** a query with no priority declaration, **When** it fetches, **Then** its requests emit `X-Priority: high`.
3. **Given** a query declared background, **When** it is invoked from multiple call sites, **Then** every fetch inherits `low` without changing any call site.

---

### User Story 3 - Watched live-status data stays `high` (Priority: P2)

Live-status data the user is actively watching — task list, task status, proposed-change details/events, branch action state — keeps emitting `high` even though it polls on a timer. Recurring/background-*shaped* traffic that the user is nonetheless watching must not be mistaken for background work and demoted.

**Why this priority**: These polls are the classic trap: they look background-ish (recurring, unattended-seeming) but the user is watching the result in real time. Demoting them would make watched data go stale under load — the opposite of the feature's intent. Equal in importance to Story 2 because it guards the correctness boundary of the `low` class.

**Independent Test**: Assert that the specific watched-status queries (task list, task status, proposed-change details/events, branch action state) emit `X-Priority: high`, not `low`, despite polling.

**Acceptance Scenarios**:

1. **Given** a watched live-status poll (task list, task status, proposed-change details/events, or branch action state), **When** it fetches on its polling interval, **Then** it emits `X-Priority: high`.
2. **Given** the watched-status query set, **When** the codebase is audited, **Then** none of these queries is declared `low`.

---

### User Story 4 - The header survives request rebuilds (Priority: P2)

The priority header is preserved across paths that rebuild an outbound request: a 401→token-refresh replay and a file upload (which uses a separate transport path). No interactive request silently degrades to `normal` because it was reconstructed.

**Why this priority**: These rebuild paths are where a naively-injected header is silently dropped, reintroducing exactly the `normal` traffic the feature eliminates. Guarding them is required for the "no regression" success criterion but is a narrower slice than the default itself.

**Independent Test**: Force a 401 that triggers a token-refresh replay and separately perform a file upload; assert the replayed request and the upload request both still carry their `X-Priority` value.

**Acceptance Scenarios**:

1. **Given** an in-flight request that receives a 401 and is replayed after a token refresh, **When** the replay is emitted, **Then** it re-carries the same `X-Priority` value as the original.
2. **Given** a file upload, **When** it is emitted on the upload transport path, **Then** it carries `X-Priority: high` (or `low` if the upload query is declared background).

---

### User Story 5 - Cross-origin deployment accepts the header (Priority: P2)

An operator runs the frontend on a different origin than the API (dev, or a split-host deployment). The browser sends a CORS preflight; the API's CORS response permits `x-priority`, so the request carrying the header succeeds instead of being rejected by the browser.

**Why this priority**: Production is normally same-origin (the API serves the frontend) and won't preflight, so this can pass in prod and silently fail in dev/split-host — the classic "passes in prod, fails in dev" trap. It is a correctness requirement for the header to be usable at all in cross-origin deployments, and it is the one backend change that must ship with the frontend change.

**Independent Test**: Issue an OPTIONS preflight for a request that will carry `X-Priority` and assert the response's `Access-Control-Allow-Headers` permits `x-priority`; then issue the cross-origin request carrying the header and assert it succeeds.

**Acceptance Scenarios**:

1. **Given** a cross-origin frontend, **When** the browser sends the CORS preflight for a request carrying `X-Priority`, **Then** the API's CORS response allow-lists `x-priority`.
2. **Given** the preflight succeeded, **When** the cross-origin request carrying `X-Priority` is sent, **Then** it is accepted and processed.

---

### User Story 6 - Operator confirms adoption via metrics (Priority: P3)

An operator inspects `/metrics` and sees frontend traffic showing up as an explicit priority: the backend's no-priority / invalid-priority counter sits at approximately zero for frontend-origin traffic, confirming that the frontend has adopted the header everywhere.

**Why this priority**: This is an observability/verification outcome rather than a runtime behavior the user experiences. It is valuable for rollout confidence but is a consequence of Stories 1–5 being correct rather than an independent build target.

**Independent Test**: With the feature live, drive representative frontend flows and observe that the backend's no/invalid-priority counter attributable to frontend-origin traffic stays at ~0.

**Acceptance Scenarios**:

1. **Given** the feature is deployed, **When** the frontend issues its normal mix of requests, **Then** the backend's no/invalid-priority counter for frontend-origin traffic is ~0.

---

### Edge Cases

- **Token-refresh replay** rebuilds the request → it MUST re-carry the header (covered by Story 4).
- **File uploads** use a separate transport path → they MUST carry the header (covered by Story 4).
- **Cross-origin preflight** → `x-priority` MUST be allow-listed; prod is usually same-origin and won't preflight, so this must be verified explicitly for dev + split-host (covered by Story 5).
- **A watched poll** must resolve to `high`, not `low`, despite being recurring/background-shaped (covered by Story 3).
- **Requests to non-Infrahub external hosts** (e.g. git providers) MUST NOT receive `X-Priority` — the header must not leak to third parties (FR-007).
- **An invalid or unknown opt-in value** at a query definition MUST NOT emit anything other than `high` or `low`; the only two emittable values are `high` and `low`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The frontend MUST attach `X-Priority: high` by default to every request it emits across all three transports (GraphQL, REST client, raw fetch). *Verify*: intercept an outbound request on each transport; assert `high` with no opt-out required at the call site.
- **FR-002**: A developer MUST be able to declare a query `low` via a single opt-in at its definition; that query's requests emit `X-Priority: low` and all its fetches inherit the value. *Verify*: a declared query emits `low`; an undeclared query emits `high`; no call-site change is needed to inherit `low`.
- **FR-003**: The frontend MUST NOT emit any `X-Priority` value other than `high` or `low` (never `normal`, never unheadered) on any frontend-originated request. *Verify*: audit/test across all transports that no path emits `normal` or omits the header.
- **FR-004**: The header MUST survive request-rebuild paths — token-refresh (401) replay and file uploads. *Verify*: force a 401→refresh replay and an upload; assert the header is preserved with its original value.
- **FR-005**: Live-status polls the user watches — task list, task status, proposed-change details/events, and branch action state — MUST emit `high`. *Verify*: assert `high` on those queries specifically; confirm none is declared `low`.
- **FR-006**: The API MUST include `x-priority` in its CORS allowed-headers default so cross-origin frontends can send it. *Verify*: an OPTIONS preflight permits `x-priority`; a cross-origin request carrying it succeeds.
- **FR-007**: Outbound requests to non-Infrahub hosts MUST NOT receive `X-Priority`. *Verify*: a request to an external host carries no priority header.

### Key Entities *(include if feature involves data)*

- **`X-Priority` header** *(existing, backend-parsed)*: a request header parsed server-side into `high` / `normal` / `low`. This feature makes the frontend a first-class emitter of it, using only the `high` / `low` subset. No schema or contract change — the server already parses it.
- **`RequestPriority`** *(new, frontend)*: the typed `'high' | 'low'` union that models the emittable priority contract, plus its default (`high`). Type-safe; not a stringly-typed value (Constitution III).
- **CORS allowed-headers list** *(existing, backend config)*: the API's CORS allowed-headers default, extended by exactly one value (`x-priority`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (coverage)**: 100% of frontend-originated requests carry an explicit `high` or `low` value; the backend's no/invalid-priority counter for frontend-origin traffic sits at ~0.
- **SC-002 (correctness)**: `low` is emitted only by the declared background/preload set; everything the user waits on or watches (including watched live-status polls) is `high`.
- **SC-003 (no regression)**: the header survives replay and upload paths; no interactive request degrades to `normal` after a rebuild.
- **SC-004 (joint outcome — not a v1 blocker)**: with the backend admission layer (IFC-2886) live, interactive frontend requests hold bounded latency / ~0 shed rate under saturating background load, while background-tagged frontend requests shed first. This is a joint outcome with the backend and is a validation target, not a gate for shipping this frontend change.

## Assumptions

- **Cooperative first-party trust model** (inherited from IFC-2886): the frontend's `high` claim is accepted by the backend; there is no enforcement that a `high` claim is legitimate in v1.
- **Production is normally same-origin** (the API serves the frontend and won't preflight); cross-origin is mainly dev and some split-host deployments — still a correctness requirement satisfied via CORS (FR-006).
- **The concrete `low` set is small (possibly empty) today**: the deliverable is the *mechanism* and *convention*, not a large enumeration. Any concrete background/preload query identified during implementation is demoted to `low`, but no large-scale sweep is required. *(Resolves PRD open question: initial `low` set may be empty in v1.)*
- **The `low` opt-in is a single unified developer-facing helper** that covers both a GraphQL operation `context`-based declaration and a REST per-request option, so one convention serves all transports. *(Resolves PRD open question: exact shape of the `low` opt-in — the precise API surface is finalized in the plan step.)*
- **The three transports are the complete set of frontend request origins**: GraphQL client, REST client, and raw fetch. Any request the frontend emits flows through one of these.
- **The CORS change is security-adjacent and ships with this feature**: adding `x-priority` to the CORS allowed-headers default is flagged for review per AGENTS.md "Ask First"; it is additive (one header value) and introduces no new endpoint or contract.
- **SC-001 is validated against a global (unlabeled) counter**: the backend's `infrahub_admission_missing_priority_total` counter has no origin dimension, so "for frontend-origin traffic" cannot be sliced out directly. Adoption is confirmed by (a) the global counter trending toward its non-frontend floor (SDK/other callers) as the frontend stops emitting unheadered/`normal` requests, and (b) the per-transport E2E/unit assertions proving every frontend request carries an explicit `high`/`low`. Adding an origin label to the counter is out of scope for v1 (a backend/IFC-2886 observability concern).

## Out of Scope

- Enforcing that a `high` claim is legitimate (deferred with IFC-2886 — cooperative trust model in v1).
- SDK / background-worker `Retry-After` backoff behavior (backend/SDK-owned).
- Building a prefetch/preload system — this feature only ensures such loads are *born* `low` when they arrive; it does not create them.
- Large-scale enumeration or demotion of existing loads to `low`.
- Any GraphQL schema change, new endpoint, or new API contract — the feature adds a request header the server already parses.

## Governance Gates Crossed

| Gate | Crossed? | Notes |
|------|----------|-------|
| Database schema or migration change | No | — |
| API / public interface change | No | Adds a request header the server already parses; no schema/contract change |
| New dependency | No | — |
| CI/CD workflow change | No | — |
| **CORS / security-adjacent config change** | **YES** | Add `x-priority` to the API's CORS allowed-headers default. Ships *with* the frontend change; flagged for review per AGENTS.md "Ask First." |

## Constitution Alignment

- **III — Type Safety & Explicit Contracts**: `RequestPriority` is a typed `'high' | 'low'` union, not a stringly-typed value; the emittable contract is explicit.
- **IV — Test Discipline**: every FR carries a one-line verification; header behavior is asserted per transport and per query class, including a backend contract test for CORS and an E2E scenario covering interactive vs background traffic.
- **VII — Simplicity & Maintainability**: one automatic default (`high`) plus one opt-in (`low`), not a per-call priority taxonomy; the mechanism is delivered without a large enumeration.
