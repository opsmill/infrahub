# Feature Specification: Priority-aware API backpressure (server-side)

**Feature Branch**: `dga/feat-rate-limiting-api-zb38x`

**Created**: 2026-07-10

**Status**: Extracted

**Source**: Jira Story [IFC-2886](https://opsmill.atlassian.net/browse/IFC-2886) — implements JPD idea INFP-636 (API Request Prioritization)

**Input**: PRD "Priority-aware API backpressure (server-side)" from IFC-2886

> **Amendment (post-implementation)**: the middle priority tier was renamed `normal` → `medium` during implementation. This spec predates the rename and calls it `normal` throughout — read `normal` as `medium`. The database-stress signal (which augments CoDel with a reference-query load measurement) was also added after this spec. Both are documented in [dev/knowledge/backend/api-backpressure.md](../../knowledge/backend/api-backpressure.md).

## Overview

When an Infrahub instance runs heavy background work (generators, artifacts, diffs, repository syncs, computed attributes) while a human uses the frontend, both compete for the same finite uvicorn worker pool and the same Neo4j connection pool. Background tasks call back into the same API servers over HTTP via the SDK, and today the API has no prioritization and no origin awareness — frontend and background requests are indistinguishable. Under heavy background load the API can no longer serve the frontend and the application appears unresponsive or hangs.

This feature adds a **server-side admission layer** that sheds load *by priority*. Each request declares a priority via an `X-Priority` header (`high`/`normal`/`low`); the server admits high-priority (interactive) requests first and sheds low-priority (background) requests first when overloaded. Shedding is adaptive — driven by how long requests actually wait for capacity (sojourn time), not a fixed threshold — and a shed request receives a fast, honest `429 Too Many Requests` + `Retry-After` instead of the server accepting work it cannot finish. The frontend stays responsive regardless of background volume, with no per-customer tuning.

**Scope boundary**: This specification covers the **server side only**. The client/SDK backoff that consumes `Retry-After`, the frontend setting `X-Priority: high`, and enforcement that a `high` claim is legitimate are all tracked separately (see Out of Scope).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Frontend stays responsive under background overload (Priority: P1)

An Infrahub instance is under heavy background load (saturating generators/diffs/syncs). A human uses the frontend — loads a page, edits an object, views a diff — and those requests carry `X-Priority: high`. The interactive requests are served with bounded latency while low-priority background requests are shed with `429 + Retry-After`.

**Why this priority**: This is the entire point of the feature and its only user-visible guarantee. Without it, heavy background work makes the product appear hung. It is independently valuable and demonstrable on its own — the rest of the requirements (observability, tuning-free operation) support or prove this outcome.

**Independent Test**: Drive a saturating stream of `low` requests plus an interactive stream of `high` requests at an instance; confirm `high` requests are admitted and served with bounded latency while `low` requests receive `429 + Retry-After`, and the `high` shed rate stays ≈ 0%.

**Acceptance Scenarios**:

1. **Given** background load saturating the API, **When** an interactive request tagged `X-Priority: high` arrives, **Then** it is admitted and served while concurrent `low` requests receive `429 + Retry-After`, and the `high` shed rate stays ≈ 0%.
2. **Given** the API is not overloaded, **When** requests of any priority arrive, **Then** all are admitted and served (shedding is inactive).
3. **Given** sustained overload has ended, **When** offered load drops below capacity, **Then** shedding stops on its own within a bounded window and all classes are served again.

---

### User Story 2 - Declare request priority via header (Priority: P1)

Any caller (frontend, SDK, background worker) can declare a request's priority by setting the `X-Priority` header to `high`, `normal`, or `low`. The server classifies the request solely from this header. A missing or invalid value is treated as `normal`, so the mechanism is safe to deploy before any caller is updated.

**Why this priority**: The admission layer cannot prioritize anything without a priority signal. This is the contract every other requirement builds on, and its safe default (`normal`) is what lets the feature ship inert.

**Independent Test**: Send requests with `X-Priority: high`, `normal`, `low`, an invalid value, and no header; confirm each is classified as the expected class (invalid/missing → `normal`) and that a no-header request succeeds normally when the server is not overloaded.

**Acceptance Scenarios**:

1. **Given** a request with `X-Priority: high` (or `normal`, or `low`), **When** it is received, **Then** it is classified into the matching priority class.
2. **Given** a request with no `X-Priority` header or an empty/malformed value, **When** it is received, **Then** it is classified as `normal` and served normally when capacity allows.

---

### User Story 3 - Background callers shed fast instead of hanging (Priority: P2)

A background/SDK caller issuing `low`-priority work against an overloaded instance is shed with a fast `429 + Retry-After` rather than left to hang waiting for capacity the server cannot provide. The shed happens without executing the request handler, so no server work is wasted on a request that will not complete.

**Why this priority**: A fast honest rejection is the mechanism that both protects capacity and gives background callers a signal to retry later. It depends on Stories 1 and 2 being in place but is a distinct, testable behaviour (the *shape* of the rejection).

**Independent Test**: Under overload, issue a `low` request and confirm the response is `429` with a `Retry-After` header and that the request handler never ran (no side effects, no downstream DB work).

**Acceptance Scenarios**:

1. **Given** the server sheds a request, **When** it responds, **Then** the response is `429 Too Many Requests` with a `Retry-After` header and no handler work was performed.
2. **Given** a shed occurs, **When** the response is emitted, **Then** it is tagged with a shed reason (`codel` or `backstop`) for observability.

---

### User Story 4 - Tuning-free operation across deployment sizes (Priority: P2)

An operator deploys Infrahub on a small, medium, or large instance and the protection works without hand-tuned limits. The per-worker concurrency cap is derived from per-process signals (the process's own Neo4j client-pool size), not a hard-coded constant, and shedding adapts to observed wait times rather than a fixed threshold.

**Why this priority**: "No per-customer tuning" is a core promise. If the cap were a magic number, the feature would misbehave on differently-sized deployments and require support intervention. It is testable independently of the load behaviour by verifying the derivation.

**Independent Test**: Configure two different per-process Neo4j pool sizes and confirm the effective `max_concurrency` resolves from that signal (no magic constant) and is reported via metrics.

**Acceptance Scenarios**:

1. **Given** a per-process Neo4j client-pool size, **When** the worker initializes, **Then** the effective `max_concurrency` is derived from that signal (no hard-coded constant) and exposed as a metric.
2. **Given** a burst of load shorter than the congestion interval, **When** it arrives, **Then** it is absorbed with zero sheds (adaptive, not fixed-threshold).

---

### User Story 5 - Per-priority observability on /metrics (Priority: P2)

An operator inspects the existing `/metrics` endpoint and sees, per priority class: offered load, admissions, rejections split by reason, live queue depth and in-flight count, and the wait-time (sojourn) distribution — plus the effective derived concurrency cap and a count of requests arriving with no/invalid priority header. This lets the operator see contention, prove the mechanism works, and track caller adoption of the header.

**Why this priority**: Observability is how the operator confirms the P1 guarantee is actually holding and how the team proves the shed gradient. It is required for the success criteria to be measurable, but the protection itself functions without an operator watching.

**Independent Test**: Drive mixed-priority traffic through the admission layer and scrape `/metrics`; confirm every required metric family is present with the correct labels and that counts move as expected (offered, admitted, rejected-by-reason, waiters/in-flight, sojourn histogram, derived cap, no-priority count).

**Acceptance Scenarios**:

1. **Given** mixed-priority traffic, **When** `/metrics` is scraped, **Then** it exposes per-class offered / admitted / rejected(by reason) / in-flight / waiters / sojourn-distribution series, the derived `max_concurrency`, and the no/invalid-priority count.
2. **Given** requests arrive with no `X-Priority` header, **When** `/metrics` is scraped, **Then** the no/invalid-priority counter reflects them so adoption can be tracked.

---

### Edge Cases

- **Client disconnect while queued** (including the same tick a slot was handed to the waiter): the waiter deregisters and re-releases any handed slot — no leaked slot, no deadlock.
- **Burst shorter than the congestion `interval`**: absorbed, zero sheds (CoDel does not drop for a sub-interval burst).
- **Empty or malformed `X-Priority`**: treated as `normal`.
- **Untrusted `X-Priority`**: any caller can claim `high`; accepted as a v1 assumption under a cooperative first-party trust model (enforcement deferred — see Out of Scope).
- **Overload ends**: shedding self-terminates within a bounded window (a single below-target sample exits the dropping state).
- **Low-priority starvation under sustained overload**: accepted as a deliberate consequence of strict priority; made observable via the per-class rejection and sojourn metrics rather than prevented in v1.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST bound concurrent in-handler requests per worker via a slot pool. *Verify*: offered load above the cap causes waiting/shedding, never unbounded admission.
- **FR-002**: System MUST use sojourn time (the time a request waited to acquire a slot) as the load signal, measured by acquiring a real slot. *Verify*: slower handler work produces larger measured sojourn.
- **FR-003**: System MUST shed adaptively per class via a CoDel-style controller (`target`/`interval`); a burst shorter than `interval` MUST NOT be shed. *Verify*: fake-clock unit test — a sub-interval burst yields zero drops.
- **FR-004**: System MUST hand a freed slot to the highest-priority waiter, FIFO within a class. *Verify*: slot-pool unit test on cross-class priority ordering and within-class FIFO.
- **FR-005**: System MUST run one CoDel controller per class such that `low` sheds first, `normal` after, and `high` last (with extra protection). *Verify*: load test shows the shed gradient (`low` before `normal` before `high`).
- **FR-006**: System MUST classify a request solely on the `X-Priority` header; a missing or invalid value MUST map to `normal`. *Verify*: a request with no header is treated as `normal` and succeeds when capacity allows.
- **FR-007**: System MUST return `429 + Retry-After` for every shed request without executing the handler. *Verify*: the shed response carries `Retry-After` and does no handler work.
- **FR-008**: System MUST release slots in a `finally` block and handle waiter cancellation (client disconnect) without leaking slots. *Verify*: cancellation-cleanup unit test — no leaked slots, no deadlock.
- **FR-009**: System MUST derive per-worker `max_concurrency` from per-process signals (the process's own Neo4j client-pool size), not a hard-coded constant, with no replica-aware coordination. *Verify*: the cap resolves from config/per-process signals with no magic number and is exposed via FR-OBS-6.

#### Observability Requirements

- **FR-OBS-1**: System MUST expose offered requests per priority class (Counter, label `priority`).
- **FR-OBS-2**: System MUST expose `429`s per class split by reason (Counter, labels `priority` and `reason` ∈ {`codel`, `backstop`}).
- **FR-OBS-3**: System MUST expose live waiters and in-flight count per class (Gauge, label `priority`).
- **FR-OBS-4**: System MUST expose the sojourn-time distribution per class (Histogram, label `priority`) so P50/P99 and the shed gradient are visible.
- **FR-OBS-5**: System MUST expose admitted requests per class (Counter, label `priority`).
- **FR-OBS-6**: System MUST expose the effective derived `max_concurrency` (Gauge).
- **FR-OBS-7**: System MUST expose a count of requests arriving with no/invalid `X-Priority` header (Counter).
- **FR-OBS-8**: All observability defined above MUST be exported through the existing `/metrics` endpoint (no new endpoint).

### Key Entities

- **Priority class** *(new)*: a `high`/`normal`/`low` enum (lower ordinal = higher priority); in-process, per worker.
- **Priority slot pool** *(new)*: a bounded concurrency primitive (semaphore) with one waiter queue per class; hands a freed slot to the highest-priority waiter, FIFO within a class; in-process, per worker; cancellation-safe.
- **CoDel controller** *(new)*: a pure per-class shedding state machine with an injected clock, deciding shed/serve from observed sojourn against `target`/`interval`.
- **Admission middleware** *(new)*: sits in the existing API middleware stack; the request's admission decision point; wires the header parser, slot pool, per-class CoDel, and backstop, and emits `429 + Retry-After` on shed.
- **Backpressure metrics** *(new)*: Prometheus metric families (FR-OBS-1…8) on the existing `/metrics` endpoint.
- **Capacity derivation** *(new)*: resolves per-worker `max_concurrency` from the per-process Neo4j client-pool size.
- **API request** *(existing)*: gains an `X-Priority` request-header contract and a possible `429 + Retry-After` outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (headline, discovery-measured): On a defined test scenario, high-priority request latency holds steady while background traffic is shed. Concrete latency bounds are set from measurement on that scenario, not pre-committed, so the guarantee holds across deployment sizes without a hard-coded target. The discovery scenario MUST additionally confirm that, under that overload, the load signal (slot-wait / sojourn) actually rises — i.e. slot contention binds before the database saturates silently — so the mechanism sheds rather than admitting into a slow backend. *(The scenario and the measured bounds are defined during implementation — see Assumptions.)*
- **SC-002**: Under sustained overload, the `high` shed rate is ≈ 0%, `low` is the first class shed, and `normal` sheds only after `low` (an observable shed gradient).
- **SC-003**: A burst shorter than the congestion interval produces zero sheds.
- **SC-004**: Every shed is a fast `429 + Retry-After` with no handler work performed.
- **SC-005**: After overload ends, shedding stops on its own within a bounded window (no manual intervention).
- **SC-006**: The admission layer is inert on a default deployment — with no caller setting `X-Priority`, all traffic is classified `normal` and behaviour is unchanged from today until load actually exceeds the derived cap.

## Assumptions

- **Cooperative trust model**: Callers are trusted first-party (Infrahub's own frontend and workers); `X-Priority` is cooperative, not adversarial. There is no enforcement in v1 that a `high` claim is legitimate. (Constitution VI — Security & Input Boundaries: the header is untrusted client input, and enforcement is a deliberately deferred fast-follow.)
- **Neo4j provisioning is an operator responsibility**: The Neo4j server is provisioned for peak aggregate load (per-process cap × workers × max replicas). The middleware does not compute or coordinate this.
- **Ships inert**: The mechanism defaults all traffic to `normal` until callers set the header (frontend → `high`, background → `low`); it changes no behaviour until load exceeds the derived per-worker cap.
- **SC-001 bounds are discovery-measured**: The headline latency bound is quantified from a discovery test scenario during implementation rather than pre-committed here, so it holds across deployment sizes without a hard-coded target.
- **Existing infrastructure is reused**: The middleware extends the existing API middleware stack, the metrics extend the existing `/metrics` Prometheus stack, and `prometheus_client` is already a dependency. CoDel is implemented in-house (no new dependency).
- **Per-worker, coordination-free**: Admission state is in-process per worker; there is no shared/global limiter and no replica-aware coordination (Constitution VII — Simplicity).
- **Slot contention is the binding constraint**: The load signal is the time a request waits for a concurrency slot (sojourn). For shedding to trigger under real overload, the derived per-worker cap must be reached *before* the database saturates — i.e. slot contention must bind before Neo4j does. The derivation assumes roughly one database connection per in-flight request; a headroom factor (default 1.0, tunable below 1.0) is the lever to pull the cap under raw pool size if a deployment saturates the database first. This is validated by the SC-001 discovery scenario, not assumed blindly.
- **Rollout is kill-switch-guarded and sequenced with the frontend**: The P1 "frontend stays responsive" guarantee is only fully realized once the frontend sends `X-Priority: high` (a separate ticket). Shipping enabled beforehand means interactive traffic is classified `normal` and, under overload, is shed on the same footing as background `normal` traffic (hangs become fast `429`s rather than protected requests). This is a deliberate, operator-reversible choice: an enable/disable switch defaults on but can bypass the layer entirely, so the layer can be validated (and the frontend updated) before relying on it for interactive protection.

## Out of Scope

- Client/SDK backoff that consumes `Retry-After` (tracked in separate, in-progress tickets).
- The frontend setting `X-Priority: high` (a separate client-side effort).
- Making the existing DB-level throttle priority-aware (fast-follow).
- Token-type classification and `X-Priority` enforcement — i.e. verifying a `high` claim is legitimate (fast-follow, pairs with the trust-model gap).
- Weighted fairness / anti-starvation for low priority (v1 accepts strict priority).
- Replica-aware global capacity coordination.
- Any GraphQL schema change and any data/persistence change (none required).

## Governance Gates Crossed

- **[x] API / public interface change** — new `X-Priority` request header and `429 + Retry-After` response behaviour across endpoints; flag in review.
- **[x] Authentication / authorization change (borderline)** — no auth logic changes, but the admission middleware sits in the request-admission path and consumes a client-controlled header; heads-up in review, no redesign.
- **[ ] Database schema or migration change** — not crossed (HTTP-only in v1).
- **[ ] New dependency** — not crossed (`prometheus_client` already present; CoDel is custom).
- **[ ] CI/CD workflow change** — not crossed.

## Dependencies

- Existing API middleware stack (the admission middleware extends it).
- Existing `/metrics` Prometheus endpoint and `prometheus_client` (metrics extend it; prior art: `database/metrics.py`, `graphql/metrics.py`).
- Per-process Neo4j client-pool size as the capacity-derivation signal.
- Related work (not blocking): complementary task-queue ordering (GitHub #9785); GitHub tracking issue #9852; client-side backoff in separate tickets.
