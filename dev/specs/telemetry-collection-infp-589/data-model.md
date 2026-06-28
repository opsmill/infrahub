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

| Field                     | Type          | Meaning                                                  | Empty | Failure |
|---------------------------|---------------|---------------------------------------------------------|-------|---------|
| `logins`                  | `int \| None` | `account.logged_in` events in the trailing 24h          | `0`   | `null`  |
| `unique_logins`           | `int \| None` | Distinct `account_id` among those logins (same window)  | `0`   | `null`  |
| `webhooks_fired_success`  | `int \| None` | `webhook-process` flow runs in 24h ending `COMPLETED`   | `0`   | `null`  |
| `webhooks_fired_failure`  | `int \| None` | `webhook-process` flow runs in 24h ending `FAILED`/`CRASHED`/`TIMEDOUT` | `0` | `null` |

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
