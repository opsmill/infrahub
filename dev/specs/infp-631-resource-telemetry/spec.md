# Feature Specification: Licensing Resource-Allocation Telemetry

**Feature Branch**: `resource-telemetry-infp-631`

**Created**: 2026-07-20

**Status**: Extracted

**Input**: User description: "Licensing resource-allocation telemetry (Phase 1 extension of INFP-589 daily anonymous telemetry) — add per-component cores and RAM to the telemetry payload so a deployment can be audited against its sold tier."

## User Scenarios & Testing *(mandatory)*

Infrahub is sold in tiers (small / medium / large) priced on the compute allocated to the deployment. Today the daily telemetry snapshot describes host and database facts but not how much compute is actually allocated to each Infrahub component, so no one can tell from telemetry whether a deployment is running within the tier it pays for. These journeys close that gap for the licensing and customer-success audience. This is an internal auditing capability; it is not visible to end users of Infrahub.

### User Story 1 - Audit a deployment against its contracted tier (Priority: P1)

A customer-success or licensing reviewer opens a deployment's most recent telemetry snapshot and reads the compute allocated to Infrahub — cores and memory for the database, and for the API server and the task workers as one worker's share times the number of active workers — then compares those figures against the tier the customer contracted for, flagging deployments that are over- or under-provisioned.

**Why this priority**: This is the entire reason the feature exists. Without it, tier compliance can only be established by contacting the customer or inspecting their environment directly. It is the minimum viable slice: a snapshot that carries allocated cores and memory per component already delivers the audit.

**Independent Test**: Produce a telemetry snapshot on a running deployment and confirm it contains, for each of the three components, the cores available, cores assigned, total memory, and available (free) memory, all in comparable units — for the API server and the task workers as one worker's share of its container, alongside the count of active workers — and that a reviewer can compare those figures to a tier definition without any further data.

**Acceptance Scenarios**:

1. **Given** a deployment whose database is allocated 32 cores while contracted for a 4-core "small" tier, **When** the daily telemetry snapshot is produced, **Then** the snapshot reports 32 available database cores, so the audit shows the deployment exceeds its tier without contacting the customer.
2. **Given** a running deployment, **When** the snapshot is produced, **Then** it reports cores and memory for the database, the API server, and the task workers, with all core counts expressed in the same unit, so the database figures and each other component's per-worker share multiplied by its active count are directly comparable.

---

### User Story 2 - Audit an offline / air-gapped deployment (Priority: P2)

A reviewer needs to audit a deployment that never transmits telemetry — because it is air-gapped or has opted out of remote reporting — using only the snapshot the deployment retains locally (obtained via a support export or backup).

**Why this priority**: The majority of the customer base runs disconnected, so an audit path that depends on transmission would miss most deployments. It builds directly on P1 but is independently valuable and independently testable.

**Independent Test**: Configure a deployment to opt out of remote telemetry, produce a snapshot, and confirm the locally retained snapshot still contains the full resource-allocation section.

**Acceptance Scenarios**:

1. **Given** a deployment that has opted out of remote telemetry, **When** the snapshot is produced, **Then** the resource-allocation metrics are present in the locally stored snapshot even though nothing is transmitted.

---

### User Story 3 - Preserve the audit when a source cannot be read (Priority: P3)

When one resource source cannot be read (a limit is unreadable, a database setting read fails, or a worker fails to report), the reviewer still receives every other figure in the snapshot, and can tell that a value is genuinely unknown rather than zero. A failure of the database's own system-information read is the exception: it predates this feature and still aborts the snapshot.

**Why this priority**: Resilience protects the audit's trustworthiness across a heterogeneous fleet, but the core value (P1/P2) is deliverable before every degradation edge is polished.

**Independent Test**: Force a single resource source to fail and confirm the snapshot is still produced and stored, that only the figures depending on that source carry no value, and that every other field is intact.

**Acceptance Scenarios**:

1. **Given** one resource source that cannot be read, **When** the snapshot is produced, **Then** only the figures that depend on it report no value — the database's assigned cores alone; both CPU figures of a worker's reading for an unusable CPU limit; both memory figures for an unusable memory limit; free memory alone for unreadable usage — every other field is present, and the snapshot is still produced and stored.
2. **Given** a component where one active worker fails to report its resources after retries, **When** the snapshot is produced, **Then** the worker count still includes that worker and the per-worker figures come from a worker that did report, rather than reporting no value. That worker is still counted as a sharer of its container, so where processes share a container the per-worker share does not read high. The one exception is a worker that cannot read even its container's name.

### Edge Cases

- **No allocation limit configured**: when a component runs with no enforced compute limit, its "assigned" figures report no value (null) rather than being back-filled with the "available" amount, so an unlimited deployment is distinguishable from a limited one.
- **No active workers**: when no process of a component is heartbeating, its `active` count is zero and its per-worker figures are no value. Its `total` can stay non-zero for up to two hours, because an exited process's schema-hash keys, which name its component, outlive its heartbeat.
- **Database unreachable**: the snapshot is not produced. The rest of the snapshot surviving is the intent, but not yet the behaviour: the database gather and its system-information read are not wrapped in the per-metric degradation boundary (a gap that predates this feature). Only the new assigned-cores read is guarded on its own. `database.system_info` reports no value only when the database is not Neo4j. Closing the gap is a tracked follow-up.
- **Consumer on an older payload version**: the new fields ship additively under the existing payload version (`20260628`), so older ingestion ignores what it does not recognise rather than break; the version bump is a gated follow-up once the receiving service confirms it tolerates the new fields.
- **Partial worker reporting**: some workers report and some do not — the per-worker share comes from a worker that reported, and the count reflects all active workers. A process that has not reported is not counted as a sharer of its container, so a shared container's share reads high until it does; each process publishes a reading at startup, so for a new process this lasts briefly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The telemetry snapshot MUST report, for the database, the API server, and the task workers, the logical processor cores available, the logical processor cores assigned, the total memory, and the available (free) memory — the database's own figures, and for the API server and the task workers one worker's share of its container (FR-004) — extending the existing database section in place and adding a dedicated section each for the API server and the task workers (no standalone "resources" block). The existing worker section is unchanged. Memory usage is derived as total − available (as the database already does).
- **FR-002**: Core counts MUST be expressed as logical processor units — the unit in which compute is provisioned and licensed — consistently across all three components, so the figures are comparable to each other and to a tier definition once a per-worker share is multiplied by its active count. A per-worker share of cores may be fractional. Physical-core counts MUST NOT be used. The new fields MUST reuse the existing system-information field names (`processor_*` / `memory_*`) so every component is represented identically.
- **FR-003**: For each component, the "assigned" cores MUST report the enforced CPU allocation limit when one is configured, and MUST report no value (null) when no limit is configured; it also reports no value when the limit cannot be read. For the API server and the task workers, cores available with no assigned value means no limit is enforced, and both with no value means the limit could not be read or no process of that component reported a reading. The system MUST NOT substitute the "available" amount for a missing limit. Memory has no equivalent "assigned" figure — a configured memory limit surfaces as the component's total (capacity) figure instead.
- **FR-004**: The task-worker section MUST report the number of task-worker processes and one task worker's share of its container's resources, rather than a per-process or per-container breakdown; the API server section MUST do the same for API server processes. The share is the most complete reading of the component divided by the number of processes that reported from the same container, so the share multiplied by the active count is the component's total, assuming every replica of a component runs with the same configuration. Each section's count and resources MUST describe the same component. The existing worker section MUST keep counting every worker process. The two new counts add up to it, except for a process that can no longer be matched to a component, which only the worker section counts. That is a process that stopped about two hours earlier: the keys naming its component have expired, but its 2-hour presence key has not yet, normally for the last 15 minutes or so before Infrahub forgets it (research D17).
- **FR-005**: Each API server and task-worker process MUST read its own resources and report what it could read, with every failure logged as a warning so the gap can be traced back. Two levels apply:
  - The whole self-read is attempted up to 3 times with no delay between attempts. In practice only the read of the process's identity (hostname, host CPU count) can make it fail. If all attempts fail, the process reports a reading with no figures that still names its container, and logs a warning carrying the component type, the worker identity, and the error text.
  - A failure of one source inside the read is caught there, with no retry, and nulls only the figures that depend on it: an unusable CPU limit file nulls both CPU figures; an unusable memory limit file or a failed host-memory capacity read nulls both memory figures; an unreadable usage file or a failed host free-memory read nulls free memory alone. Its warning carries the file path (or the error text, for a host-memory read) and the host, but not the component.

  The database figures are not retried; a failed assigned-cores read reports no value and logs the generic per-metric warning. The worker count MUST continue to reflect all active workers, including one whose reading is missing or failed.
- **FR-006**: Each resource source MUST be read independently, so the failure of one source yields no value only for the figures that depend on it (FR-005) and never omits other fields or prevents the snapshot from being produced and stored. A failed scan of the worker readings nulls every per-worker figure in both the task-worker and API server sections. The database's assigned-cores read is guarded on its own. This holds for every source read by this feature. It does not hold for the database's existing system-information read and the database gather around it, which predate this feature and are not guarded: a Neo4j or JMX failure aborts the snapshot (see Edge Cases). The worker-count read, which also predates this feature, is not guarded either, so a cache failure there aborts the snapshot as well.
- **FR-007**: The resource-allocation metrics MUST be present in the locally stored snapshot regardless of whether the deployment has opted out of remote telemetry transmission.
- **FR-008**: All payload changes MUST be additive — no existing field renamed, removed, retyped, or given a new meaning. New information goes into new sections. The payload version identifier MUST be incremented only after the receiving service confirms it tolerates the new fields; until then the new fields ship additively under the existing version, so existing ingestion is never broken.

### Key Entities *(include if feature involves data)*

- **Component resource figures**: for one component (database, API server, or task workers), the four figures — cores available, cores assigned, total memory, available (free) memory — each of which may be a measured number or "no value" when it cannot be determined or does not apply. Memory usage is derived as total − available.
- **Placement**: database figures extend the database's existing system-information; the API server and the task workers each gain a new section; the existing worker section is unchanged. No standalone "resources" section is introduced.
- **Per-worker share**: for the API server and the task workers, the four figures of one worker's share of its container: the most complete reading of the component divided by the number of processes that reported from the same container. Multiplied by the section's active count it gives the component's total. Each new section has its own `total`/`active`, counted the same way as the existing worker section's but for one component only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of deployments running the release, a single telemetry snapshot contains the CPU cores available to (and, once a limit is set, assigned to) the database, the API server, and the workers, plus their memory — for the API server and the workers as a per-worker share and an active count — enabling a tier comparison with no customer contact.
- **SC-002**: A reviewer can determine whether the database cores available to a deployment exceed its contracted tier from one snapshot, in zero customer round-trips.
- **SC-003**: The metrics are available for offline / air-gapped deployments (approximately 75% of the customer base) from the locally retained snapshot, requiring no network transmission.
- **SC-004**: A failure in any single resource source read by this feature nulls only the figures that depend on it — the database's assigned cores, one CPU pair or one memory pair (or free memory alone) of a worker's reading, or every per-worker figure when the scan of readings fails — and never prevents the snapshot from being produced or stored. The database's existing system-information read and the worker-count read are outside this guarantee: both predate this feature, and a failure in either aborts the snapshot.
- **SC-005**: The change removes, renames or retypes no field already present in the telemetry payload, and no existing field changes meaning: `workers.total`/`active` still count every worker process.

## Assumptions

- **Units**: core counts are logical processor units and memory is reported in bytes, matching the database system-information figures the payload already carries, so all figures are internally consistent.
- **Reported components**: the database, the API server, and the task workers are the resource-bearing components relevant to tier sizing. Which of them define a given tier is a separate product decision (see Out of Scope) — all three are collected regardless, so that decision does not block collection.
- **Self-observation**: each component can observe its own allocation limit and usage from its runtime environment; where the environment enforces no limit, "assigned" is genuinely undefined and is reported as no value.
- **No enforcement today, but some limits are configured**: Infrahub enforces no tier. The database's "assigned" figure reads the Neo4j `server.cypher.parallel.worker_limit` setting, which the `infrahub-enterprise` chart presets set to the preset's CPU request (4, 8 or 16, infrahub-helm#93); an install from those presets reports its sized database cores, and one that leaves the setting at its default `0` (auto) reports no value. The setting caps the Cypher parallel runtime's workers, not Neo4j's total CPU use, so it is a sized budget rather than an enforced ceiling. The server and worker "assigned" figures read the container CPU quota directly, so a deployment running under a container CPU limit reports a finite value. Every "assigned" field self-populates as its own limit becomes configured, with no change to the payload shape. This supersedes the expectation recorded on INFP-589 (2 July) that the configured database count would "usually equal the physical count": where the setting is unset it is reported as no value rather than as the physical figure, and where a preset sets it, it is the preset's figure rather than the node's.
- **Worker signal**: the per-worker share is computed from separate resource keys, which each process writes in the same heartbeat as its active-worker key and with the same 15-second expiry. The readings are not filtered against the active-worker set that telemetry already uses to count workers.
- **Retries**: a small, bounded number of retries is sufficient for a component to read its own resources; beyond that, reporting a reading with no figures, which the per-worker share leaves out, is preferred over blocking or failing the snapshot.
- **Receiving service** (cross-team dependency): the new fields ship additively under the existing payload version, so existing ingestion keeps working without any receiving-service change. The payload-version increment itself is a gated follow-up, applied only once the receiving service confirms it tolerates the new fields.
- **No new third-party package** is required — but not by falling back to raw syscalls: host cores and memory are read through `psutil`, which gives a cleaner, cross-platform interface. `psutil` was already pinned in `pyproject.toml` but only in the dev group; it is promoted to a runtime dependency (production images previously lacked it entirely — see research D1) rather than added as a brand-new package. Only the container CPU/memory *limit* (which `psutil` does not expose) is read from the standard library (`/sys/fs/cgroup`, located through `/proc/self/cgroup`), along with the container name (the hostname and the PID namespace from `/proc/self/ns/pid`).
- **Net-new vs the existing payload**: the payload already reports database cores-available + memory and the worker count. This feature adds the database's "assigned" figure in place and two new sections, for the API server and the task workers, each with its own count and per-worker CPU/RAM. The new counts break the existing worker count down by component; the worker count itself is unchanged. No parallel "resources" section is introduced.

## Out of Scope

- **Enforcing** or limiting compute allocation (a later licensing phase, INFP-472) — this feature only reports.
- The **license file / entitlement mechanism** (INFP-633).
- **Per-container or per-process** resource breakdown — each section reports one worker's share, taken from one representative reading, not a row per container or per process.
- **Deciding the tier basis** (database-only versus database + workers + server) — a product decision; this feature collects all three so the decision can be made later from real data.
- Other Phase-2 telemetry signals (for example API-token, CLI, or query usage).
- Changes to the telemetry-**receiving** service and data store; those are coordinated separately as a cross-team dependency.
