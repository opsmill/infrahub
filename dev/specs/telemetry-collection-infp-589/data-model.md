# Phase 1 Data Model: Phase 1 Telemetry Collection

This feature adds no database schema entities. The "data model" here is the **telemetry
payload model** (Pydantic models in `backend/infrahub/telemetry/models.py`). All changes are
additive.

## New models

### `TelemetryAccountData`

| Field    | Type         | Meaning                                            | Empty | Failure |
|----------|--------------|----------------------------------------------------|-------|---------|
| `active` | `int \| None`| Count of `CoreAccount` with `status == ACTIVE`     | `0`   | `null`  |
| `groups` | `int \| None`| Count of `CoreAccountGroup`                        | `0`   | `null`  |

Counts via `NodeManager.count` on the default branch (branch/temporal-correct).

### `TelemetryActivity24hData`

The window is the **previous full UTC calendar day** `[window_start, window_end)` where
`window_end = floor_to_midnight_utc(now)` and `window_start = window_end - 24h` — anchored to a
deterministic calendar boundary, NOT to gather-time `now`, so consecutive daily runs tile
exactly (no overlap, no gap) despite the jittered cron minute and execution drift.

| Field                     | Type          | Meaning                                                  | Empty | Failure |
|---------------------------|---------------|---------------------------------------------------------|-------|---------|
| `logins`                  | `int \| None` | `account.logged_in` events in the windowed day          | `0`   | `null`  |
| `unique_logins`           | `int \| None` | Distinct `account_id` among those logins (same window)  | `0`   | `null`  |
| `webhooks_fired_success`  | `int \| None` | `webhook-process` flow runs in-window ending `COMPLETED`| `0`   | `null`  |
| `webhooks_fired_failure`  | `int \| None` | `webhook-process` flow runs in-window ending `FAILED`/`CRASHED`/`TIMEDOUT` | `0` | `null` |

Each field is isolated: one failing source nulls only its own field. A `webhook-process` run
that started in-window but is still non-terminal (`PENDING`/`RUNNING`/`SCHEDULED`) at gather
time is counted in neither success nor failure — only terminal outcomes are tallied (a
best-effort daily trend signal).

## Extended models

### `TelemetryBranchData` (extended)

| Field    | Type          | Status     | Meaning                                                       |
|----------|---------------|------------|--------------------------------------------------------------|
| `total`  | `int`         | unchanged  | Existing total branch count (`len(registry.branch)`).        |
| `active` | `int \| None` | **new**    | Open non-system branches (exclude `main` / `-global-`). `0` empty, `null` failure. |

### `TelemetryDatabaseData.node_count` (value type widened)

| Key            | Type widening                | Status     | Meaning                                                      |
|----------------|------------------------------|------------|-------------------------------------------------------------|
| `node_count`   | `dict[str, int]` → `dict[str, int \| None]` | **widened** | Holds existing keys (`total`, graph labels) + new `corenode`. |
| `…["total"]`   | `int`                        | unchanged  | Raw vertex total (`count_nodes(db)`).                       |
| `…["corenode"]`| `int \| None`                | **new key**| Managed-node count via `NodeManager.count(CoreNode)`. `0` empty, `null` failure. |

Widening is additive in practice: existing keys are always populated `int`; only `corenode`
may be `null`. No existing key changes meaning or name (FR-011).

**Three node metrics, defined at the namespace level (FR-009).** `CoreNode` is applied to every
node outside the `Schema`/`Internal` namespaces (and non-groups), so the three nest strictly —
`user ⊆ corenode ⊆ total`:

| Key | Counts | Namespace scope |
|-----|--------|-----------------|
| `total` | raw vertices (incl. attributes/values/internal bookkeeping) | n/a (raw graph) |
| `corenode` | all managed nodes (this phase) | `Core` + `Builtin` + user-defined |
| `user` (future, IFC-2825) | customer-facing subset | excludes `Core` management namespace; `Builtin` in/out is the parked decision |

Because the `Core` management namespace (accounts, repositories, proposed changes, webhooks,
profiles, …) is always non-empty and is always in `corenode` but never in `user`, the two can
never collapse into the same value. Pinning these definitions here prevents a later `user`
definition from becoming a synonym for `corenode` (which FR-011 would then make unremovable).

### `TelemetryData` (root, extended)

| Field          | Type                       | Status  |
|----------------|----------------------------|---------|
| `accounts`     | `TelemetryAccountData`     | **new** |
| `activity_24h` | `TelemetryActivity24hData` | **new** |
| `branches`     | `TelemetryBranchData`      | extended (see above) |
| `database`     | `TelemetryDatabaseData`    | extended (node_count) |
| *(all other existing fields)* | unchanged   | unchanged |

The two new root objects are always present; per-metric nullability lives on their fields, so
a whole-source failure surfaces as nulled fields, never a missing object (SC-001).

## Validation / invariants

- **Additive**: no existing field renamed, retyped (except the documented `node_count` value
  widening), or removed (FR-011).
- **null vs 0**: `null` ⇔ source raised; `0` ⇔ source succeeded with nothing to count
  (FR-010, SC-001).
- **Windowing**: event/flow-run metrics count only records whose occurrence/start is within
  the trailing 24h (SC-002).
- **Branch-correct**: `corenode`, `accounts.*` computed on the default branch via
  `NodeManager.count` (Constitution II); `corenode` must equal an independently-computed
  fixture exactly (SC-003).

## Out of model (this phase)

- `database.node_count["user"]` — blocked (IFC-2825), not added.
- No changes to `TelemetryPrefectData.events` (the existing unwindowed tally).
