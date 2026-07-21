# Feature Specification: Licensing Resource-Allocation Telemetry

**Feature Branch**: `resource-telemetry-infp-589`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Licensing resource-allocation telemetry (Phase 1 extension of INFP-589 daily anonymous telemetry) — add per-component cores and RAM to the telemetry payload so a deployment can be audited against its sold tier."

## User Scenarios & Testing *(mandatory)*

Infrahub is sold in tiers (small / medium / large) priced on the compute allocated to the deployment. Today the daily telemetry snapshot describes host and database facts but not how much compute is actually allocated to each Infrahub component, so no one can tell from telemetry whether a deployment is running within the tier it pays for. These journeys close that gap for the licensing and customer-success audience. This is an internal auditing capability; it is not visible to end users of Infrahub.

### User Story 1 - Audit a deployment against its contracted tier (Priority: P1)

A customer-success or licensing reviewer opens a deployment's most recent telemetry snapshot and reads the compute allocated to Infrahub — cores and memory for the database, the API server, and the worker fleet — then compares those figures against the tier the customer contracted for, flagging deployments that are over- or under-provisioned.

**Why this priority**: This is the entire reason the feature exists. Without it, tier compliance can only be established by contacting the customer or inspecting their environment directly. It is the minimum viable slice: a snapshot that carries allocated cores and memory per component already delivers the audit.

**Independent Test**: Produce a telemetry snapshot on a running deployment and confirm it contains, for each of the three components, the cores available, cores assigned, memory available, and memory used, all in comparable units — and that a reviewer can compare those figures to a tier definition without any further data.

**Acceptance Scenarios**:

1. **Given** a deployment whose database is allocated 32 cores while contracted for a 4-core "small" tier, **When** the daily telemetry snapshot is produced, **Then** the snapshot reports 32 available database cores, so the audit shows the deployment exceeds its tier without contacting the customer.
2. **Given** a running deployment, **When** the snapshot is produced, **Then** it reports cores and memory for the database, the API server, and the worker fleet, with all core counts expressed in the same unit so they are directly comparable.

---

### User Story 2 - Audit an offline / air-gapped deployment (Priority: P2)

A reviewer needs to audit a deployment that never transmits telemetry — because it is air-gapped or has opted out of remote reporting — using only the snapshot the deployment retains locally (obtained via a support export or backup).

**Why this priority**: The majority of the customer base runs disconnected, so an audit path that depends on transmission would miss most deployments. It builds directly on P1 but is independently valuable and independently testable.

**Independent Test**: Configure a deployment to opt out of remote telemetry, produce a snapshot, and confirm the locally retained snapshot still contains the full resource-allocation section.

**Acceptance Scenarios**:

1. **Given** a deployment that has opted out of remote telemetry, **When** the snapshot is produced, **Then** the resource-allocation metrics are present in the locally stored snapshot even though nothing is transmitted.

---

### User Story 3 - Preserve the audit when a source cannot be read (Priority: P3)

When one component or one metric cannot be determined (a source is unreachable, a limit is unreadable, or a worker fails to report), the reviewer still receives every other figure in the snapshot, and can tell that a value is genuinely unknown rather than zero.

**Why this priority**: Resilience protects the audit's trustworthiness across a heterogeneous fleet, but the core value (P1/P2) is deliverable before every degradation edge is polished.

**Independent Test**: Force a single resource source to fail and confirm the snapshot is still produced and stored, that only the affected field carries no value, and that every other field is intact.

**Acceptance Scenarios**:

1. **Given** one resource metric that cannot be read, **When** the snapshot is produced, **Then** only that field reports no value, every other field is present, and the snapshot is still produced and stored.
2. **Given** a worker fleet where one active worker fails to report its resources after retries, **When** the snapshot is produced, **Then** the reported worker count still includes that worker while the aggregated resources sum only the workers that reported (an undercount), so the discrepancy is detectable.

### Edge Cases

- **No allocation limit configured**: when a component runs with no enforced compute limit, its "assigned" figures report no value (null) rather than being back-filled with the "available" amount, so an unlimited deployment is distinguishable from a limited one.
- **No active workers**: when no workers are heartbeating, the worker count is zero and the aggregated worker resources are no value (the aggregate cannot tell a genuinely empty fleet from one where nothing reported; in practice at least one worker always runs).
- **Database unreachable**: the database resource figures degrade to no value while the rest of the snapshot is still produced.
- **Consumer on an older payload version**: the receiving service must tolerate the new section; the version increment and additive-only fields let older ingestion ignore what it does not recognise rather than break.
- **Partial worker reporting**: some workers report and some do not — the aggregate reflects only reporters, the count reflects all active workers.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The telemetry snapshot MUST report, for the database, the API server, and the worker fleet, the logical processor cores available, the logical processor cores assigned, the total memory, and the available (free) memory — extending the existing database and worker sections in place and adding a dedicated section for the API server (no standalone "resources" block). Memory usage is derived as total − available (as the database already does).
- **FR-002**: Core counts MUST be expressed as logical processor units — the unit in which compute is provisioned and licensed — consistently across all three components, so the figures are directly comparable to each other and to a tier definition. Physical-core counts MUST NOT be used. The new fields MUST reuse the existing system-information field names (`processor_*` / `memory_*`) so every component is represented identically.
- **FR-003**: For each component, the "assigned" cores and memory MUST report the enforced allocation limit when one is configured, and MUST report no value (null) when no limit is configured. The system MUST NOT substitute the "available" amount for a missing limit.
- **FR-004**: The worker section MUST report the number of active workers and the aggregate (sum) of their resources across the fleet, rather than a per-worker breakdown.
- **FR-005**: Each component MUST attempt to determine its own resources, retrying a bounded number of times, before reporting; if determination still fails it MUST report no value for the affected fields **and MUST log a warning that identifies the component and the failing source, so the gap can be traced back**. The worker aggregate MUST sum whatever workers reported (an undercount is acceptable) while the worker count MUST continue to reflect all active workers, so an undercount is detectable.
- **FR-006**: Each resource metric MUST be collected independently, so the failure of any one metric yields no value for only that field and never omits other fields or prevents the snapshot from being produced and stored.
- **FR-007**: The resource-allocation metrics MUST be present in the locally stored snapshot regardless of whether the deployment has opted out of remote telemetry transmission.
- **FR-008**: All payload changes MUST be additive — no existing field renamed, removed, or retyped. The payload version identifier MUST be incremented only after the receiving service confirms it tolerates the new fields; until then the new fields ship additively under the existing version, so existing ingestion is never broken.

### Key Entities *(include if feature involves data)*

- **Component resource figures**: for one component (database, API server, or worker fleet), the four figures — cores available, cores assigned, total memory, available (free) memory — each of which may be a measured number or "no value" when it cannot be determined or does not apply. Memory usage is derived as total − available.
- **Placement**: database figures extend the database's existing system-information; worker-fleet figures extend the existing worker section; the API server gains a new dedicated section. No standalone "resources" section is introduced.
- **Worker-fleet aggregate**: the summed resource readings across the task-worker fleet (deduplicated by host). The worker count is the existing active/total worker count, not a new field.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of deployments running the release, a single telemetry snapshot contains the CPU cores available to (and, once enforced, assigned to) the database, the API server, and the workers, plus their memory — enabling a tier comparison with no customer contact.
- **SC-002**: A reviewer can determine whether the database cores available to a deployment exceed its contracted tier from one snapshot, in zero customer round-trips.
- **SC-003**: The metrics are available for offline / air-gapped deployments (approximately 75% of the customer base) from the locally retained snapshot, requiring no network transmission.
- **SC-004**: A failure in any single resource source reduces a snapshot's resource coverage by at most one field, and never prevents the snapshot from being produced or stored.
- **SC-005**: The change removes or alters no field already present in the telemetry payload; every field previously emitted is still emitted unchanged.

## Assumptions

- **Units**: core counts are logical processor units and memory is reported in bytes, matching the database system-information figures the payload already carries, so all figures are internally consistent.
- **Reported components**: the database, the API server, and the worker fleet are the resource-bearing components relevant to tier sizing. Which of them define a given tier is a separate product decision (see Out of Scope) — all three are collected regardless, so that decision does not block collection.
- **Self-observation**: each component can observe its own allocation limit and usage from its runtime environment; where the environment enforces no limit, "assigned" is genuinely undefined and is reported as no value.
- **No enforcement today**: Infrahub does not currently enforce a core limit on any component, so every "assigned" figure is expected to report no value in this release. The fields are included now as forward-compatible placeholders that begin reporting real numbers automatically once per-tier enforcement is introduced — with no change to the payload shape.
- **Worker signal**: the worker aggregate is assembled from the same active-worker liveness signal telemetry already relies on to count workers.
- **Retries**: a small, bounded number of retries is sufficient for a component to read its own resources; beyond that, an undercount is preferred over blocking or failing the snapshot.
- **Receiving service** (cross-team dependency): the telemetry-receiving service will be updated to tolerate the new section and the payload-version increment. Until then, additive-only fields and the version bump keep existing ingestion working.
- **No new third-party dependency** is required — but not by falling back to raw syscalls: host cores and memory are read through `psutil`, which is already a direct dependency and gives a cleaner, cross-platform interface. Only the container CPU/memory *limit* (which `psutil` does not expose) is read from the standard library (`/sys/fs/cgroup`), along with the host id. Nothing is added to the dependency set.
- **Net-new vs the existing payload**: the payload already reports database cores-available + memory and the worker count. This feature extends those sections in place — adding only the database's "assigned" figure and the worker fleet's CPU/RAM — and adds one new section for the API server. No parallel or duplicate section is introduced.

## Out of Scope

- **Enforcing** or limiting compute allocation (a later licensing phase, INFP-472) — this feature only reports.
- The **license file / entitlement mechanism** (INFP-633).
- **Per-worker** resource breakdown — only the fleet aggregate is reported.
- **Deciding the tier basis** (database-only versus database + workers + server) — a product decision; this feature collects all three so the decision can be made later from real data.
- Other Phase-2 telemetry signals (for example API-token, CLI, or query usage).
- Changes to the telemetry-**receiving** service and data store; those are coordinated separately as a cross-team dependency.
