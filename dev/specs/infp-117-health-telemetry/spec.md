# Feature Specification: Health-Status Telemetry

**Feature Branch**: `jpd-117-health-check-endpoint`
**Created**: 2026-06-18
**Status**: Draft
**Ticket**: infp-117 (JPD-117)
**Input**: Attach a point-in-time health snapshot to each anonymous telemetry payload, so OpsMill can see when a deployment's backing services are degraded. Reuse the exact check set the `/api/health` endpoint uses. Aggregate/historical health is out of scope.

## Clarifications

### Session 2026-06-18

- Q: How should the health section be structured in the telemetry payload — an ordered list of per-dependency records, or a dictionary keyed by dependency name? → A: An ordered **list** of per-dependency records (each with name, status, and error category) plus an overall status and timestamp — the same shape the live health endpoint returns. This matches the existing telemetry convention where collections of structured records use a list (e.g. database servers, work pools), reserving name-keyed dictionaries for scalar counts.
- Q: When health gathering fails entirely, should the payload omit the section or include an explicit "unavailable" marker? → A: **Omit** the section (the field is null/absent). The payload-format version bump signals that a new-version payload intends to carry health, so absence in such a payload means "not reported this cycle." No separate "unknown" overall status is introduced.
- Q: Should the telemetry health gather use the same per-check timeout as the live health endpoint, or a separate one? → A: **Reuse** the same single, configurable per-check timeout the endpoint uses (default 3 seconds). No separate timeout is introduced for the background telemetry path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Backing-service health visible in telemetry (Priority: P1)

When a deployment sends its periodic anonymous telemetry, OpsMill receives the deployment's current backing-service health — an overall status plus a per-dependency status for each service Infrahub needs to serve traffic. This lets OpsMill notice when a customer's deployment is running in a degraded state without needing direct access to that deployment.

**Why this priority**: This is the entire value of the feature. Without it, a degraded deployment that still emits telemetry looks identical to a healthy one. It is the JPD's "proactively see if a customer encounters an issue" idea in its lowest-effort form.

**Independent Test**: On a deployment where one backing service is unavailable, trigger a telemetry gather and inspect the resulting payload. The health section is present, the affected dependency is reported as down, and the overall status is unhealthy.

**Acceptance Scenarios**:

1. **Given** a deployment whose backing services are all reachable, **When** telemetry is gathered, **Then** the payload contains a health section with an overall status of healthy and every checked dependency reported as up.
2. **Given** a deployment where one backing service is unreachable, **When** telemetry is gathered, **Then** the payload contains a health section where that dependency is reported as down with a categorized reason and the overall status is unhealthy.

---

### User Story 2 - Telemetry stays reliable when health probing fails (Priority: P2)

Telemetry collection continues to function even when health probing itself fails or a dependency is unreachable. A problem while gathering health never prevents the rest of the telemetry payload from being recorded and sent.

**Why this priority**: Health data is an addition to an existing, relied-upon pipeline. It must not become a new way for telemetry to break — that would reduce overall visibility instead of increasing it.

**Independent Test**: Force health gathering to raise an error, then run a telemetry gather. A telemetry snapshot is still produced and sent, with the health section omitted (null/absent), and the rest of the payload intact.

**Acceptance Scenarios**:

1. **Given** health gathering raises an unexpected error, **When** telemetry is gathered, **Then** the telemetry snapshot is still created, stored, and (subject to opt-out) sent, with the health section omitted (null/absent).
2. **Given** a single dependency probe exceeds its time budget, **When** telemetry is gathered, **Then** that dependency is reported as down for the reason "timeout" and all other dependencies and payload fields are reported normally.

---

### User Story 3 - Telemetry health matches the live endpoint (Priority: P3)

The health reported in telemetry reflects the same set of dependencies and the same status semantics as the live health endpoint, so the two are directly comparable and cannot drift apart over time.

**Why this priority**: Consistency makes the data trustworthy and prevents future maintenance traps where a dependency is added to one path but not the other.

**Independent Test**: For the same deployment state, compare the dependency set and status values produced for telemetry against those returned by the live health endpoint; they match.

**Acceptance Scenarios**:

1. **Given** the live health endpoint checks a defined set of dependencies, **When** telemetry health is gathered for the same deployment, **Then** the dependency set and the meaning of each status value are identical.
2. **Given** a dependency is later added to the health check set, **When** the change is made in one place, **Then** both the endpoint and the telemetry payload report the new dependency without separate edits.

### Edge Cases

- A backing service is partially initialized when telemetry runs → that dependency is reported as not-initialized rather than causing the gather to fail.
- The deployment has opted out of remote telemetry → the health section is still recorded in the locally stored snapshot but is not transmitted, consistent with existing opt-out behavior.
- The remote ingestion service receives the new, larger payload → the added health section is additive and flagged by a payload-format version change so the receiver can recognize it.
- Telemetry only runs while the worker that gathers it is operational, so a point-in-time read is biased toward "healthy"; trend detection is explicitly deferred (see FR-010).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each anonymous telemetry payload MUST include a health section describing the deployment's backing-service health at the moment the payload was gathered.
- **FR-002**: The health section MUST report an overall status and a per-dependency status for every backing service the live health endpoint checks (database, message bus, cache, task manager, and task-manager database).
- **FR-003**: Each per-dependency entry MUST include the dependency identity, an up/down status, and a categorized reason when it is down.
- **FR-004**: The set of dependencies checked and the status semantics MUST be a single source of truth shared with the live health endpoint, so adding or changing a dependency updates both the endpoint and the telemetry payload together.
- **FR-005**: The live health endpoint's externally observable behavior and response MUST remain unchanged by this feature.
- **FR-006**: A failure while gathering health MUST NOT prevent the rest of the telemetry payload from being gathered, stored, or sent; in that case the health section MUST be omitted (null/absent), and no separate "unknown" overall status is introduced. (A *single* dependency timing out is not a failure of the section — that dependency is reported as down with reason "timeout"; see FR-003.)
- **FR-007**: The telemetry payload-format version MUST be incremented to reflect the added health section.
- **FR-008**: The health section MUST NOT expose secrets, connection strings, hostnames, stack traces, or any internal implementation detail — only categorized status and reason values, consistent with the endpoint's "no internal details" guarantee.
- **FR-009**: Remote transmission of health data MUST honor the existing telemetry opt-out: when a deployment has opted out, health is recorded in the locally stored snapshot but not transmitted.
- **FR-010**: Aggregated and historical health (per-dependency uptime, failure counts over an interval, time-to-recovery) is OUT OF SCOPE for this feature and MUST be addressed by a separate follow-up item.

### Key Entities *(include if feature involves data)*

- **Telemetry Health Snapshot**: The health portion of an anonymous telemetry payload. Carries an overall status, the time the checks ran, and an ordered list of dependency health entries (the same structure the live health endpoint returns).
- **Dependency Health Entry**: A single backing service's result — its identity, an up/down status, and a categorized reason when down.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of telemetry payloads from a fully reachable deployment include a health section in which every checked dependency is reported as up and the overall status is healthy.
- **SC-002**: When a backing service is unavailable at gather time, it is reported as down with overall status unhealthy in the next telemetry payload that deployment produces.
- **SC-003**: Telemetry payloads continue to be produced and sent in 100% of cases where health gathering fails — no regression in telemetry delivery compared to before this feature.
- **SC-004**: The dependency set reported in telemetry exactly matches the dependency set returned by the live health endpoint, with zero drift, verified by an automated test.
- **SC-005**: No health field in any telemetry payload contains free-form error text, credentials, hostnames, or connection details — verified by a test asserting only categorized values are present.
- **SC-006**: All pre-existing telemetry tests pass without changes to their payload expectations beyond accommodating the new optional field.
- **SC-007**: Adding health gathering increases the telemetry gather time by no more than one configured per-check timeout window (default 3 seconds) in the worst case, including when a dependency is unreachable — because the dependency checks run concurrently, not sequentially.

## Assumptions

- The feature reuses the existing anonymous-telemetry pipeline (gather → store snapshot → conditional remote send) and the existing health check set; no new collection schedule or storage is introduced.
- The health snapshot is point-in-time, captured by the periodic telemetry gather that runs on a worker. Because the gather only runs while that worker is operational, a single reading is biased toward "healthy"; this is accepted for this iteration, and trend/uptime analysis is deferred to the follow-up named in FR-010.
- The remote telemetry ingestion service (OpsMill-side, outside this repository) tolerates an additive payload field guarded by a payload-format version change. **This must be confirmed with the telemetry-ingestion owners before release**; it is the primary external risk.
- Anonymous-telemetry semantics are unchanged: no customer-identifying data is added, and the existing deployment identifier remains the only identifier in the payload.
- Existing telemetry opt-out controls whether the health data is transmitted remotely; local snapshot storage behavior is unchanged.
- The telemetry health gather reuses the live health endpoint's single configurable per-check timeout (default 3 seconds); no separate background timeout is introduced. Checks run concurrently, so the worst-case added latency is one timeout window.
