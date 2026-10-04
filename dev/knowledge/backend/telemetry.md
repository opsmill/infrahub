# Telemetry

> Part of: `dev/knowledge/backend/` | Related: [Events System](events.md), [Asynchronous Tasks](async-tasks.md), [Licensing](licensing.md)

Infrahub gathers a usage snapshot once a day. The snapshot is always stored locally
(so air-gapped and opted-out deployments still retain their own history) and, unless the
operator opts out, is also sent to the OpsMill telemetry endpoint. It exists to understand
adoption and scale, never to capture customer data. A snapshot from Infrahub Community is
anonymous. A deployment that requires a license also reports its license ID, which OpsMill can map
to the customer it issued the license to, so that snapshot is not anonymous. It never carries the
customer name (see [License block](#license-block)).

## Collection flow

A daily Prefect flow (`anonymous_telemetry_send`, cron ~02:00 UTC with a per-deployment random
minute) gathers the payload, stores it as a `TelemetrySnapshot`, then conditionally sends it:

```text
anonymous_telemetry_send (daily)
  └─ build_anonymous_telemetry_gatherer() → AnonymousTelemetryGatherer.gather() → TelemetryData
       └─ TelemetrySnapshot.save()        ← ALWAYS stored locally first
            └─ opted out?  → mark "skipped"
               opted in?   → POST to endpoint → mark "sent" / "failed"
```

The random cron minute spreads load across deployments; it is why the windowing below is
anchored to a calendar boundary rather than to the moment the flow happens to run.

## What is collected — by category

The payload groups metrics into categories. Fields are documented in the payload contract; the
distinction that matters operationally is each category's **temporal model** (below).

| Category | What it covers |
|----------|----------------|
| Deployment | anonymous deployment id, Infrahub version/type, Python/platform |
| Workers | worker pool size and active count |
| Branches | total and open (non-system) branch counts |
| Accounts | active accounts, account groups |
| Schema | node/generic kind counts, last schema change |
| Features | how many objects of adoption-signalling kinds exist (artifacts, repos, generators, …) |
| Database | database type, node/relationship counts, server + host system info |
| Prefect | event tally, automation counts, work-pool state |
| Activity (24h) | logins, checks, artifacts, branch actions, webhook deliveries |
| License | license state, ID, type, tiers, dates and issuer; `null` when no license is required |

### Activity (24h) field semantics

| Field | Counts |
|-------|--------|
| `logins` / `unique_logins` | Interactive sign-ins only — password, OIDC, OAuth2. Per-request API-key/token authentication is stateless and never emits a login event, so token-authenticated SDK/CI traffic is **not** included. |
| `checks_started` / `_passed` / `_failed` | Validator lifecycle events (see the checks caveat under Graceful degradation). |
| `artifacts_created` / `_updated` | Artifact lifecycle events. |
| `branches_created` / `_merged` / `_deleted` | Branch lifecycle events. |
| `webhooks_fired_success` / `_failure` | Terminal `webhook-process` flow-run states. |

### License block

`license` holds the license state of the deployment. The daily flow runs on a task worker, so
`license/reporting.py::license_block` builds it from the task worker's license service:

| Field | Value |
|-------|-------|
| `state` | One of the license states (see [Licensing](licensing.md#states)) |
| `license_id` | ID of the license, set when the state carries one |
| `license_type` | Type exactly as the license states it, normally `evaluation` or `commercial` |
| `product_tier` / `support_tier` | Tiers the license grants |
| `starts_at` / `ends_at` | First instant the license is valid, and the first instant it no longer is |
| `issuer` | Who issued the license |

- The customer name is never included, although the license carries it. The license ID is enough
  for OpsMill to match a snapshot to the license it issued.
- `license` is `null` when no license is required: Infrahub Community, or an edition that registers
  no license service. For `unlicensed` and `invalid` only `state` is set, because no license was
  verified.
- The block is gathered through `safe_metric` like every other source: a block that cannot be built
  is logged and stored as `null`. A license service that raises yields `state: invalid` (see
  [Licensing](licensing.md#failure-containment)).
- It is part of the stored snapshot, so it is kept when sending is turned off and the air-gapped
  export carries it.

`TELEMETRY_VERSION` in `telemetry/constants.py` is the snapshot's `payload_format`; formats from
`20261004` carry the `license` field.

## Temporal models (the important part)

Not every number means the same thing over time. There are three kinds:

1. **Point-in-time snapshot** — most metrics (node/relationship counts, accounts, branches,
   schema, features, workers, database info, license) are the *current* value at gather time.
   Re-running the flow reflects the graph as it is now, and the license state at the task worker's
   current time.

2. **Cumulative over Prefect retention (~7 days)** — the `prefect.events` tally is a raw count
   of each event type that Prefect *still retains*. Prefect expires events after ~7 days, so
   this is a rolling window bounded by retention — **not** a per-day figure and not comparable
   day to day. This is the older, coarse signal.

3. **Windowed — previous full UTC day** — every `activity_24h.*` metric counts only events (or
   webhook flow-runs) that occurred within `[yesterday 00:00 UTC, today 00:00 UTC)`. This is the
   precise daily signal that supersedes the coarse cumulative tally for activity.

The contrast between (2) and (3) is deliberate: `prefect.events` answers "roughly how much of X
is Prefect holding right now", while `activity_24h` answers "exactly how much X happened
yesterday".

## Windowing

`get_activity_window()` returns the half-open interval `[start, end)` where `end` is midnight
UTC of the current day and `start` is 24h earlier — the previous full calendar day. Because it
is anchored to the midnight boundary (not to `now`), consecutive daily runs tile exactly with no
overlap or gap regardless of the jittered cron minute. The upper bound is exclusive; the event
counters pull their query's inclusive `until` back one microsecond so an event stamped exactly on
midnight lands in one window only, never two.

### Retention interaction

Prefect keeps events and flow-runs for ~7 days. The windowed metrics only ever look one day back,
so they are safe as long as the daily flow runs within retention (it runs every day, well inside
7 days). If the flow were down for several days, days beyond retention could not be recovered —
the metrics are a live daily sample, not a backfillable ledger.

## Graceful degradation

Every metric source is gathered through a single helper (`safe_metric`) that isolates failures:
if a source raises, that field is reported as `null` (and the failure is logged) while the rest
of the payload is still built, stored, and sent. A source that succeeds with nothing to count
reports `0`. So **`null` means "could not measure", `0` means "measured, nothing there"**.

One caveat on the check metrics: `checks_started` counts every validator that starts, but
`checks_passed`/`checks_failed` are only emitted for validators that run through the checks
runner. A validator that concludes without executing checks (a trivial no-op) is counted in
`checks_started` only, so `started` can exceed `passed + failed` without any run being
incomplete.

## Storage & access

Snapshots are stored as `TelemetrySnapshot` nodes with a `remote_send_status`
(`pending`/`sent`/`skipped`/`failed`). They are readable regardless of opt-out via
`infrahubctl telemetry list` / `infrahubctl telemetry export` or `GET /api/telemetry/snapshots`,
both gated on the `READ_TELEMETRY` global permission.

## Key Locations

| Path | Purpose |
|------|---------|
| `backend/infrahub/telemetry/tasks.py` | Daily flow, payload assembly, remote send |
| `backend/infrahub/telemetry/task_manager.py` | Windowed event / webhook-run counters |
| `backend/infrahub/telemetry/utils.py` | Degradation helper, 24h window functions, infrahub-type detection |
| `backend/infrahub/telemetry/database.py` | Database and node-count metrics |
| `backend/infrahub/telemetry/models.py` | Payload schema |
| `backend/infrahub/license/reporting.py` | License block (`license_block`) |
| `backend/infrahub/workflows/catalogue.py` | Registers the `anonymous_telemetry_send` deployment |

## See Also

- [Events System](events.md) — the Prefect events the activity metrics count
- [Asynchronous Tasks](async-tasks.md) — how the daily flow is scheduled and run
- [Licensing](licensing.md) — the license service the license block reads
