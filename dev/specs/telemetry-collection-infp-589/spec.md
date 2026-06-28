# Feature Specification: Phase 1 Telemetry Collection

**Feature Branch**: `telemetry-collection-infp-589`

**Created**: 2026-06-28

**Status**: Draft

**Input**: User description: "Phase 1 telemetry collection (epic IFC-2789, idea INFP-589). Extend Infrahub's daily telemetry payload with additive, backwards-compatible metrics for 1.11. Producer-only: add fields to the emitted/stored payload; dashboard rendering is out of scope (INFP-550 / SA-184). EXCLUDE user_node_count (blocked on a product decision — IFC-2825)."

## Overview

Infrahub emits an anonymous telemetry payload on a daily schedule. Today that
payload captures a handful of coarse counts (total branches, raw vertex count,
unwindowed Prefect event tallies). The product and data teams cannot answer
basic adoption questions from it — how many accounts are active, how the
deployment is scaling in domain terms, or what happened in the last day.

This feature extends the daily payload with a set of **additive,
backwards-compatible** metrics so the receiving data mart gains usable adoption
and scaling signals. It is **producer-only**: it changes what Infrahub emits and
stores, not how anyone visualizes it. Dashboard work (INFP-550 / SA-184) is a
separate, downstream effort.

The work is deliberately scoped as Phase 1 of a larger telemetry roadmap (epic
IFC-2789). Phase 2 metrics (licensing, token usage, generator/transformation
adoption, branch lifetime, PR governance, CLI/MCP/Sync adoption, GraphQL/REST
metrics) and the blocked `user_node_count` metric are explicitly **not** in
scope here.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Daily activity signal over a trailing 24h window (Priority: P1)

As the OpsMill data team, I need each daily telemetry payload to carry an
`activity_24h` object describing what happened in the trailing 24 hours —
logins, unique logins, and webhook successes/failures — so I can observe usage
trends per deployment instead of meaningless lifetime totals.

**Why this priority**: This is the enabler. It introduces the new windowed
event-query path, the `activity_24h` object, the `payload_format` bump, and the
graceful-degradation behavior that every other metric depends on. Without it the
other metrics have no consistent failure contract and no precedent for windowed
queries. It also delivers the highest-value signal: real daily activity.

**Independent Test**: Seed a deployment with login and webhook-process events,
some inside the trailing 24h window and some outside it, then trigger the daily
gather. The emitted payload contains an `activity_24h` object whose counts
reflect exactly the in-window events and ignore the out-of-window ones.

**Acceptance Scenarios**:

1. **Given** a deployment with login events both inside and outside the trailing
   24h window, **When** the daily telemetry payload is gathered, **Then**
   `activity_24h.logins` equals the count of in-window login events only.
2. **Given** logins from a set of distinct accounts within the window (some
   accounts logging in multiple times), **When** the payload is gathered,
   **Then** `activity_24h.unique_logins` equals the number of distinct accounts,
   not the number of login events.
3. **Given** webhook-process runs in the last 24h with a mix of successes and
   failures, **When** the payload is gathered, **Then**
   `activity_24h.webhooks_fired_success` and `activity_24h.webhooks_fired_failure`
   reflect exactly the in-window successful and failed runs respectively.
4. **Given** a deployment with zero activity in the window, **When** the payload
   is gathered, **Then** each `activity_24h` count is `0` (not `null`, not
   absent).

---

### User Story 2 - Account and branch adoption metrics (Priority: P2)

As the OpsMill data team, I need the payload to report the number of active
accounts, account groups, and currently-open non-system branches, so I can
gauge real adoption per deployment.

**Why this priority**: These are high-value adoption signals computed through
the standard branch-safe count path. They depend on the graceful-degradation
contract established in Story 1 but are otherwise independent.

**Independent Test**: Seed a deployment with a known mix of active/inactive
accounts, account groups, and open/closed/system branches, trigger the gather,
and assert each reported count matches the seeded fixture exactly.

**Acceptance Scenarios**:

1. **Given** a deployment with active and non-active accounts, **When** the
   payload is gathered, **Then** `accounts.active` equals the count of accounts
   whose status is active.
2. **Given** a known number of account groups, **When** the payload is gathered,
   **Then** `accounts.groups` equals that count.
3. **Given** open branches including the default and the global system branch,
   **When** the payload is gathered, **Then** `branches.active` counts the open
   branches while excluding the default branch and the global system branch.
4. **Given** the existing `branches.total` field, **When** the payload is
   gathered, **Then** `branches.total` is unchanged in meaning, type, and name.

---

### User Story 3 - Branch-correct scaling metric for managed nodes (Priority: P2)

As the OpsMill data team, I need a node count that reflects the number of
schema-managed nodes (the `CoreNode` generic) computed the same way the product
counts nodes, so I can measure how a deployment scales in domain terms — distinct
from the raw vertex total that includes internal graph bookkeeping.

**Why this priority**: Scaling is a primary telemetry question and the raw vertex
total is misleading for it. This metric must be computed through the
branch-safe, temporal-correct count path rather than a raw label count.

**Independent Test**: Build a fixture with a known number of managed nodes,
independently compute the expected count, trigger the gather, and assert
`database.node_count.corenode` matches the independently-computed value exactly
(±0).

**Acceptance Scenarios**:

1. **Given** a deployment with a known number of managed (`CoreNode`-generic)
   nodes, **When** the payload is gathered, **Then**
   `database.node_count.corenode` equals that count exactly.
2. **Given** the existing `database.node_count.total` raw-vertex field, **When**
   the payload is gathered, **Then** `database.node_count.total` is unchanged in
   meaning, type, and name, and the distinction between the raw total and the
   managed-node count is documented.

---

### User Story 4 - Resilient payload that never silently drops everything (Priority: P1)

As the OpsMill data team, I need the daily payload to keep arriving even when one
metric source fails, with a clear convention distinguishing "source failed" from
"genuinely zero", so I can trust field presence and interpret nulls correctly.

**Why this priority**: This is the reliability contract that makes the data
usable. Without it, one failing query could drop the whole payload, or a `null`
could ambiguously mean either "failed" or "none", corrupting trend analysis.

**Independent Test**: Force one metric's source to fail while leaving the others
healthy, trigger the gather, and assert the failed metric is `null`, every other
field is populated, and the payload is still sent/stored.

**Acceptance Scenarios**:

1. **Given** one metric source that raises an error during gathering, **When**
   the payload is gathered, **Then** that metric's field is `null`, all other
   fields are populated, and the payload is still emitted and stored.
2. **Given** a metric source that succeeds but legitimately has nothing to count,
   **When** the payload is gathered, **Then** that metric's field is `0`, not
   `null`.
3. **Given** any version of the new payload, **When** it is emitted, **Then** the
   `payload_format` identifier reflects the new payload version.

---

### User Story 5 - Depth-of-adoption activity: checks, artifacts & branch lifecycle (Priority: P2)

As the OpsMill data team, I need the daily payload to report how many validation
checks ran (and their pass/fail outcomes), how many artifacts were generated, and
how many branches were created / merged / deleted over the same trailing-24h
window, so I can measure *depth* of adoption — not just that a deployment exists,
but that its core workflows (validation, artifacts, and the branch-based change
workflow that is Infrahub's differentiator) are actively used.

**Why this priority**: These ride entirely on the windowed event path delivered by
User Story 1 — the underlying events (`validator.started/passed/failed`,
`artifact.created/updated`, `branch.created/merged/deleted`) are already emitted and
counted today, so the marginal cost is one additional event name per metric plus a
parametrized test. They serve the depth-of-adoption goal directly, making them a
near-zero-cost extension of the enabler rather than new scope of their own. Branch
*lifecycle counts* need no correlation (unlike branch *lifetime*, which is held to a
later phase).

**Independent Test**: Seed validator, artifact, and branch events inside and outside
the 24h window, trigger the gather, and assert each count reflects exactly the
in-window events.

**Acceptance Scenarios**:

1. **Given** validator events (`started`/`passed`/`failed`) inside the window,
   **When** the payload is gathered, **Then** `activity_24h.checks_started`,
   `checks_passed`, and `checks_failed` equal the in-window counts of each.
2. **Given** artifact events (`created`/`updated`) inside the window, **When** the
   payload is gathered, **Then** `activity_24h.artifacts_created` and
   `artifacts_updated` equal the in-window counts of each.
3. **Given** branch events (`created`/`merged`/`deleted`) inside the window, **When**
   the payload is gathered, **Then** `activity_24h.branches_created`,
   `branches_merged`, and `branches_deleted` equal the in-window counts of each.
4. **Given** a deployment with no such events in the window, **When** the payload
   is gathered, **Then** each of these counts is `0` (not `null`, not absent), and
   on a source failure the affected field is `null`.

---

### Edge Cases

- **Event-retention leakage**: The 24h window is far shorter than the underlying
  event retention (7 days for events, 90 days for webhook flow runs), so a correct
  window must never include retained-but-out-of-window records.
- **Window anchoring vs. jittered schedule**: The daily job runs at a per-deployment
  random minute. If the window were anchored to the job's execution time, day-over-day
  execution drift would make consecutive windows overlap (double-count) or gap (miss
  records). The window MUST therefore be anchored to a fixed calendar boundary (the
  previous full UTC day), not to execution time, so daily snapshots tile exactly.
- **Best-effort event counts**: Event dispatch can drop records, so activity
  counts are a trend signal, not a billing-grade exact count. This is acceptable
  and must be documented; success criteria for event metrics are framed around
  windowing correctness, not against an external ground truth.
- **Default and system branches**: `branches.active` must exclude the default
  branch and the global system branch; only genuinely open, non-system branches
  count.
- **Existing-field protection**: No existing field may change meaning, type, or
  name. Deprecation is allowed; removal is not.
- **Consumer compatibility**: A `payload_format` bump plus new fields must be
  tolerated by a forward-compatible consumer that ignores unknown fields.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The payload MUST report `accounts.active` as the count of accounts
  whose status is active, computed through the standard branch-safe count path.
  [IFC-2822]
- **FR-002**: The payload MUST report `accounts.groups` as the count of account
  groups. [IFC-2822]
- **FR-003**: The payload MUST report `database.node_count.corenode` as the count
  of managed (`CoreNode`-generic) nodes, computed through the branch-safe,
  temporal-correct count path (not a raw vertex/label count). [IFC-2821]
- **FR-005**: The payload MUST report `branches.active` as the count of open,
  non-system branches, excluding the default branch and the global system
  branch. [IFC-2822]
- **FR-006**: The payload MUST report `activity_24h.webhooks_fired_success` and
  `activity_24h.webhooks_fired_failure` as the counts of successful and failed
  webhook-process runs over the trailing 24h. [IFC-2824]
- **FR-007**: The feature MUST add a NEW trailing-24h-windowed event-query path
  that feeds `activity_24h`, WITHOUT modifying the existing unwindowed event
  tally output, and MUST advance the `payload_format` identifier. [IFC-2820]
- **FR-008**: The payload MUST report `activity_24h.logins` (count of login
  events over the trailing 24h) and `activity_24h.unique_logins` (distinct
  accounts over the same window). [IFC-2823]
- **FR-009**: The feature MUST NOT change the existing raw-vertex
  `database.node_count.total` field, and MUST document the distinction between the
  node metrics so they cannot later become synonyms. Definitions are operational, by
  how each is computed:
  - `total` — raw graph vertex count (includes history, all branches, and internal
    bookkeeping nodes). Unchanged by this feature.
  - `corenode` — count of nodes carrying the `CoreNode` generic label, obtained via
    the branch-safe `NodeManager.count` path (same as FR-003). By construction this
    is every schema-managed node whose namespace is not internal-only
    (`Schema`/`Internal`); it therefore includes management kinds such as
    `CoreAccount`, not just user-defined data.
  - `user` (future / blocked — IFC-2825, not in this feature) — a narrower,
    customer-facing subset of `corenode`. Its exact namespace boundary — in
    particular whether the `Builtin` namespace (tags, IPAM addresses/prefixes) counts
    as user data — is an open product decision and MUST NOT be assumed here.

  The metrics nest by construction (`user ⊆ corenode ⊆ total`), but only `total` and
  `corenode` are defined and delivered in this phase. [IFC-2821]
- **FR-010**: When a metric's source fails, that field MUST be set to `null`
  while the rest of the payload is still emitted and stored; when a source
  succeeds with nothing to count, the field MUST be `0`, not `null`. [IFC-2820]
- **FR-011**: All changes MUST be additive. No existing field may change its
  meaning, type, or name. Deprecation is permitted; removal is not.
- **FR-012**: The payload MUST report `activity_24h.checks_started`,
  `activity_24h.checks_passed`, and `activity_24h.checks_failed` as the windowed
  counts of `validator.started`, `validator.passed`, and `validator.failed` events
  respectively, via the same windowed event path as FR-007/FR-008. [INFP-589, depth-of-adoption]
- **FR-013**: The payload MUST report `activity_24h.artifacts_created` and
  `activity_24h.artifacts_updated` as the windowed counts of `artifact.created` and
  `artifact.updated` events respectively, via the same windowed event path. [INFP-589, depth-of-adoption]
- **FR-014**: The payload MUST report `activity_24h.branches_created`,
  `activity_24h.branches_merged`, and `activity_24h.branches_deleted` as the windowed
  counts of `branch.created`, `branch.merged`, and `branch.deleted` events
  respectively, via the same windowed event path. (Branch *lifetime* — create→merge
  duration — remains out of scope; it needs per-branch correlation.) [INFP-589, depth-of-adoption]

### Governance Requirement

- **GR-001**: Before shipping, the payload contract change (the `payload_format`
  bump and the new fields) MUST be confirmed compatible with the receiving end
  (the cloud telemetry processor and the downstream data mart) — specifically
  that the receiver (a) tolerates the format bump, (b) ignores unknown fields,
  and (c) tolerates `null` values on the new fields, including a `null` value on
  the new `corenode` key inside the existing `node_count` object (the only place
  a previously all-integer map can now carry a `null`). Because every change is
  additive, a forward-compatible consumer keeps working; this is a confirmation
  gate, not a code dependency.

### Key Entities *(include if feature involves data)*

- **Telemetry payload**: The daily anonymous data structure Infrahub emits and
  stores. Carries a `payload_format` version identifier and nested sub-objects
  (`accounts`, `branches`, `database`, and the new `activity_24h`).
- **`activity_24h` object**: A new sub-object holding activity counts over the
  previous full UTC calendar day (a 24h window anchored to a fixed boundary, not
  to job-execution time): `logins`, `unique_logins`, `checks_started`,
  `checks_passed`, `checks_failed`, `artifacts_created`, `artifacts_updated`,
  `branches_created`, `branches_merged`, `branches_deleted`,
  `webhooks_fired_success`,
  `webhooks_fired_failure`.
- **Node-count metrics (`database.node_count`)**: A map of node counts. `total` =
  raw vertices (existing, unchanged); `corenode` = `CoreNode`-generic count via the
  branch-safe count path (new, this phase). A future `user` subset is blocked
  (IFC-2825) and not added here. The map may carry a `null` only on the new
  `corenode` key (per FR-010 / GR-001).
- **Account**: A user account with a status (active vs. non-active) used for
  `accounts.active`.
- **Account group**: A grouping of accounts, counted for `accounts.groups`.
- **Branch**: A line of change. The default branch and the global system branch
  are excluded from `branches.active`.
- **Login event**: An event emitted after authentication and stored in the event
  system (not in the graph database). The source for `activity_24h.logins` and
  `unique_logins`.
- **Webhook-process run**: An execution of the webhook delivery flow, with a
  success/failure outcome, counted for the `activity_24h` webhook fields.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All in-scope fields are present on 100% of daily telemetry runs; a
  field is `null` only when its source genuinely failed, never when the source
  succeeded with nothing to count.
- **SC-002**: Event-derived metrics reflect exactly a 24h window anchored to a
  deterministic calendar boundary (the previous full UTC day), so consecutive
  daily snapshots tile with no overlap and no gap — independent of the exact
  (jittered) time the daily job runs — and with no leakage from records retained
  but outside the window. Verified with fixtures containing both in-window and
  out-of-window records.
- **SC-003**: `database.node_count.corenode` matches an independently-computed
  fixture count exactly (±0).
- **SC-004**: No existing telemetry field changes meaning, type, or name across
  this release (the `node_count` map may carry a `null` value only on the new
  `corenode` key); the `payload_format` identifier is advanced and a
  forward-compatible consumer that ignores unknown fields and tolerates `null`
  values continues to parse the payload (confirmed with the receiving team per
  GR-001).

## Assumptions

- The telemetry feature is producer-only; consuming/visualizing the new fields
  (dashboards, INFP-550 / SA-184) is out of scope and handled downstream.
- Login activity is sourced from the event system (events are emitted after
  authentication and stored there); the graph database holds no last-login
  timestamp, so a windowed event query is the correct and only source.
- The 24h window is anchored to the previous full UTC calendar day (a fixed
  boundary, not job-execution time) and is comfortably shorter than the underlying
  retention windows (7-day event retention, 90-day webhook flow-run retention), so
  all in-window records are available at gather time and consecutive daily
  snapshots tile exactly.
- Activity counts are best-effort trend signals (event dispatch can drop), not
  billing-grade exact figures; correctness is judged on windowing behavior, not
  against an external ground truth.
- Counts are gathered on the default branch through the standard branch-safe
  count path, consistent with how the product computes them elsewhere.
- The "graceful degradation" contract (per-metric isolation, `null` on failure,
  `0` on genuine empty) applies uniformly to every in-scope metric.

## Out of Scope

- `database.node_count.user` (FR-004 / IFC-2825) — blocked on a product decision
  about which namespaces to include; explicitly excluded from this feature.
- Remaining Phase 2 telemetry items: licensing (cores/RAM), distinct API-token
  usage, generators/transformations adoption, branch lifetime, PR governance,
  CLI/MCP/Sync adoption, and GraphQL/REST metrics. (Checks and artifacts, formerly
  considered Phase 2, are pulled into Phase 1 — see FR-012/FR-013 — because their
  events already flow and serve a stated Phase 1 goal.)
- **Held in Phase 2 even though their events already flow** (a bare count would be
  permanent contract surface — FR-011 — without clear standalone Phase 1 value):
  - **PR governance** — `proposed_change.*` events exist, but the useful metric
    ("merged without review") needs per-PR review↔merge correlation.
  - **Branch lifetime** — the create→merge *duration* metric needs durable per-branch
    correlation. (Branch lifecycle *counts* — created/merged/deleted — are in scope as
    `activity_24h.branches_*`, FR-014; only the duration is deferred.)
  - **Node churn** — `node.created/updated/deleted` events exist, but `node.updated`
    fires on every attribute mutation incl. automated/computed writes, so the count is
    dominated by machine activity — a noisy proxy for human adoption, not a clean
    standalone signal.
  - **Branch `rebased` / `migrated` counts** — cheap, but rebase/migration are
    maintenance/automation-driven and lower-signal than create/merge/delete; deferred
    to keep the permanent field set focused.
- Dashboard rendering and any consumer-side visualization (INFP-550 / SA-184).
- Redefining or altering the existing `database.node_count.total` raw-vertex
  metric.
- Persisting logins or any last-login state in the graph database.

## Dependencies

- **Receiving-end confirmation (GR-001)**: A confirmation gate with the
  cloud-processor and data-mart owners that the additive payload change is
  tolerated before shipping. Not a code dependency (the change is additive), but
  a release gate.
