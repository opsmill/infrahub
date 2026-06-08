# Feature Specification: Dedicated Task-Manager Backing-Store (Postgres) Health Check

**Feature Branch**: `jpd-117-health-check-endpoint`
**Created**: 2026-06-05
**Status**: Draft
**Input**: User description: "we should add an optional healthcheck for the postgres database — the task manager would be shown as unhealthy but having a dedicated healthcheck for postgres would directly point out the issue. And once this PR is merged, would be good to have a 'health dashboard' in the UI as well."

## Context

The health endpoint already reports four dependencies: the primary graph database, the message bus, the cache, and the task manager. The task manager runs on a separate backing store (a Postgres database) that it uses to persist its state. When that backing store is unavailable, the task-manager dependency is reported as unhealthy — but the report does not say *why*. An operator sees "task manager: down" and cannot tell whether the task-manager application itself is broken or whether its backing store is the root cause, which slows incident diagnosis.

This feature adds a **dedicated** health check for the task manager's backing store so the failing component is named directly in the health response. The task manager and its backing store are always part of Infrahub, so the check is **always on**; the backing store may be hosted outside the deployment (managed or external), but it is still a dependency Infrahub relies on and still has a connection target the check can probe.

> Note: this backing store is **separate** from Infrahub's primary graph database, which already has its own `database` dependency entry. This feature does not change or duplicate that check.

## Clarifications

### Session 2026-06-05

- Q: How should the backing-store check be enabled (auto-when-configured / opt-in / always)? → A: Always on — the task manager and its backing store are always part of Infrahub (the store may be hosted outside the deployment, but is still used), so the check always runs against the connection target that is configured.
- Q: Where does the API server obtain the backing-store connection details? → A: Reuse the task manager's existing database connection URL (the same connection that configures the task manager) rather than introducing a separate setting.
- Q: What is the new dependency named in the health response? → A: `task_manager_db` (role-based, consistent with the existing `task_manager` entry, not confusable with the primary `database` entry).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pinpoint a backing-store outage (Priority: P1)

An operator (or an automated monitoring system) queries the health endpoint during an incident. The task manager is failing because its backing store is unreachable. With a dedicated backing-store check, the health response names `task_manager_db` as the down dependency, so the operator immediately knows where to look instead of inferring it from the generic task-manager failure.

**Why this priority**: This is the core value of the feature — turning an ambiguous "task manager down" signal into an actionable root cause. Without it, the feature delivers nothing.

**Independent Test**: With the backing store made unreachable while the task-manager application is otherwise reachable-or-not, query the health endpoint and confirm `task_manager_db` is reported down with a classified error and the overall status is unhealthy.

**Acceptance Scenarios**:

1. **Given** the backing store is reachable, **When** the health endpoint is queried, **Then** the response includes a `task_manager_db` dependency reported as up.
2. **Given** the backing store is unreachable, **When** the health endpoint is queried, **Then** the response includes `task_manager_db` reported as down with an error category indicating the failure type, and the overall status is unhealthy.
3. **Given** the backing store is down (which also degrades the task manager), **When** the health endpoint is queried, **Then** `task_manager_db` is reported as down, making the root cause explicit rather than only surfacing the downstream `task_manager` failure.

---

### User Story 2 - Externally-hosted backing store is still monitored (Priority: P2)

An operator runs a deployment where the task manager's backing store is hosted outside the deployment (for example, a managed or external Postgres service). Because the backing store is still a dependency Infrahub uses, the check must still probe it via its configured connection target and report `task_manager_db` like any other dependency — operators get the same root-cause signal regardless of where the store runs.

**Why this priority**: It confirms the check behaves consistently whether the store is in-deployment or external, which is the common production topology. It is secondary to US1 because it shares the same reporting mechanism.

**Independent Test**: Point the configured connection target at an external backing store, query the health endpoint, and confirm `task_manager_db` appears and reflects that store's reachability.

**Acceptance Scenarios**:

1. **Given** the backing store is hosted outside the deployment but configured via the task manager's connection, **When** the health endpoint is queried, **Then** `task_manager_db` is reported with a status reflecting that external store's reachability.

---

### Edge Cases

- **Backing store unreachable (timeout vs. refused)**: `task_manager_db` is reported down with an error category that distinguishes a timeout from a refused/closed connection, consistent with the existing dependency checks.
- **Backing store reachable but task manager application down**: `task_manager_db` reports up while `task_manager` reports down — distinguishing an application failure from a backing-store failure.
- **Backing store down → task manager also down**: Both report down; `task_manager_db` identifies the upstream root cause.
- **Authentication/permission failure to the backing store**: `task_manager_db` reports down with an appropriate error category, without leaking credentials.
- **No connection target resolvable**: When the task manager's database connection cannot be resolved (no connection URL available to the application), `task_manager_db` is reported down with a not-initialized error category, surfacing the misconfiguration rather than hiding it.
- **Slow backing store**: The check is bounded by the same per-dependency timeout as the other checks and reported down on timeout rather than blocking the response.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a dedicated health check for the task manager's backing store, reported as a distinct dependency entry named `task_manager_db` in the health response (separate from the existing `task_manager` and `database` entries).
- **FR-002**: The `task_manager_db` check MUST be always enabled — it is a first-class dependency. It MUST run on every health request regardless of whether the backing store is hosted inside or outside the deployment.
- **FR-003**: The check MUST obtain its connection target by reusing the task manager's existing database connection (the same connection used to configure the task manager); it MUST NOT require a separate, independently-maintained connection setting.
- **FR-004**: When the backing store is reachable, `task_manager_db` MUST be reported as up.
- **FR-005**: When the backing store is unreachable, `task_manager_db` MUST be reported as down with an error category that classifies the failure (e.g., timeout, connection refused/closed, not initialized, unknown), consistent with the categories used by the existing dependency checks.
- **FR-006**: When no connection target can be resolved for the task manager's backing store, `task_manager_db` MUST be reported as down with a not-initialized error category (it MUST NOT be silently omitted).
- **FR-007**: The overall health status MUST incorporate the `task_manager_db` dependency — any down dependency yields an unhealthy overall status — consistent with the existing aggregation behavior.
- **FR-008**: The `task_manager_db` check MUST be bounded by the same per-dependency timeout used by the other checks and MUST run concurrently with them so it does not increase overall response time.
- **FR-009**: The health response MUST NOT expose connection strings, credentials, hostnames, ports, or database names for the backing store, consistent with the existing rule that no internal details appear in the response.
- **FR-010**: The dedicated check MUST NOT alter, remove, or duplicate the existing dependency entries (`database`, `message_bus`, `cache`, `task_manager`); it is purely additive.

### Key Entities

- **`task_manager_db` dependency entry**: A new member of the reported dependency set, carrying the same shape as existing entries — the dependency name `task_manager_db`, an up/down status, and an error category. Always present in the response.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When the task-manager backing store is unavailable, an operator can identify the backing store as the failing component directly from a single health response, with no need to inspect logs or task-manager internals.
- **SC-002**: The `task_manager_db` dependency is reported on every health request, whether the backing store is hosted inside or outside the deployment, so coverage does not depend on topology.
- **SC-003**: Adding the dedicated check does not increase the health endpoint's response time beyond the existing per-dependency timeout budget (checks run concurrently).
- **SC-004**: No backing-store connection details (credentials, host, port, database name) appear in any health response.
- **SC-005**: For an induced backing-store outage, the time for an operator to attribute the incident to the backing store drops to the time taken to read one health response (from previously requiring secondary investigation of task-manager internals).

## Out of Scope / Future Work

- **UI health dashboard** *(future, gated on this PR merging)*: A view in the web interface that surfaces the status of all reported dependencies (including `task_manager_db`) at a glance, so operators do not have to call the endpoint manually. This is explicitly deferred to a follow-up feature with its own specification and ticket, to be started once the current health-endpoint work is merged.
- Alerting, notification, or paging on dependency state changes.
- Historical health trends or uptime tracking.
- Health checks for dependencies beyond those already reported plus this backing store.

## Assumptions

- The task manager (Prefect) persists its state in a Postgres backing store; this feature's check targets that store specifically. It is distinct from Infrahub's primary graph database (Neo4j), which already has its own `database` dependency entry and is unaffected by this feature.
- The task manager and its backing store are always part of an Infrahub deployment; the store may be hosted externally, but Infrahub always has a configured connection target for it. The check is therefore always on rather than conditionally omitted.
- The check reuses the task manager's existing database connection (the same connection used to configure the task manager) to reach the backing store; it does not introduce a separate connection setting.
- The dedicated check reuses the existing health-endpoint contract: dependency name/status/error shape, overall-status aggregation, per-dependency timeout, concurrent execution, and the no-internal-details rule. It introduces one new dependency name, `task_manager_db`.
- The backing-store probe is a lightweight connectivity/liveness check (can the application reach and authenticate to the store), not a deep query of task-manager state.
- This work ships as part of the current health-endpoint PR (JPD-117); the UI dashboard is a separate, later effort.
