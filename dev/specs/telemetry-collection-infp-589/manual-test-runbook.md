# Telemetry Phase 1 — Manual Test Plan

Validates the daily telemetry payload end to end on a running Infrahub instance. It assumes you
can already spin up Infrahub (the standard dev stack via `uv run invoke dev.start`) and have an
admin API token. For the concepts behind these metrics — categories, windowing, retention,
degradation — see `dev/knowledge/backend/telemetry.md`.

## What you are validating

The Phase 1 payload additions:

- **Point-in-time**: `accounts.active`, `accounts.groups`, `branches.active`,
  `database.node_count.corenode`, `database.node_count.user` — checked against an independent
  source (GraphQL) or an invariant.
- **Windowed**: the `activity_24h.*` block (logins, checks, artifacts, branch actions, webhook
  deliveries) — checked with the bundled `window_probe.py`.

## Prerequisites

Container names below assume the default `infrahub` compose project; adjust if yours differ.

```fish
set -x INFRAHUB_ADDRESS http://localhost:8000
set -x INFRAHUB_API_TOKEN (docker exec infrahub-server-1 printenv INFRAHUB_INITIAL_ADMIN_TOKEN)
set P /source/dev/specs/telemetry-collection-infp-589/window_probe.py   # probe path inside the worker
```

The repo is bind-mounted into the worker at `/source`, so the probe runs there without copying.

## 1. Trigger a collection on demand

The flow runs daily at ~02:00 UTC; trigger it now instead of waiting:

```bash
docker exec infrahub-task-worker-1 prefect deployment run 'anonymous_telemetry_send/anonymous_telemetry_send'
```

Wait ~20s for a worker to pick it up.

> With `telemetry_optout=false` (default) this also POSTs one anonymous payload to the real
> endpoint — the same thing the daily cron does. The snapshot is stored locally *before* the
> send regardless, so inspection never depends on it. To avoid the send, set
> `INFRAHUB_TELEMETRY_OPTOUT=true` on the worker and recreate it first.

## 2. See the payload

```fish
uv run infrahubctl telemetry list        # newest row = the run you just triggered
uv run infrahubctl telemetry export --output /tmp/t.json
python3 -c "
import json
d = json.load(open('/tmp/t.json'))[0]['data']
print('accounts    :', d['accounts'])
print('branches    :', d['branches'])
print('node_count  :', {k: d['database']['node_count'][k] for k in ('total', 'corenode', 'user')})
print('activity_24h:', json.dumps(d['activity_24h'], indent=2))
"
```

## 3. Validate the point-in-time metrics

These reflect current state, so trigger a fresh snapshot (step 1) before comparing.

`accounts` — GraphQL counts must equal `accounts.active` / `accounts.groups`:

```bash
curl -s -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"query { active: CoreAccount(status__value:\"active\"){count} groups: CoreAccountGroup{count} }"}' \
  http://localhost:8000/graphql/main
```

`branches.active` — GraphQL branch list minus `main` must equal it (`branches.total` is 2 higher:
it also counts `main` and the internal `-global-` branch):

```bash
curl -s -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"query { Branch { name is_default } }"}' http://localhost:8000/graphql/main \
  | python3 -c "import sys,json;b=json.load(sys.stdin)['data']['Branch'];print('active =', len([x for x in b if not x['is_default']]))"
```

`node_count` — verify the invariant from step 2's output: `user ≤ corenode ≤ total`, and
`user < corenode` (the always-present `Core` management namespace lifts `corenode` above `user`).

## 4. Validate the windowed metrics (`activity_24h`)

`window_probe.py` counts one metric in three windows: **YESTERDAY** (what the snapshot reports),
**TODAY** (what tomorrow's snapshot will report), **LAST 3H** (fresh activity).

```bash
docker exec infrahub-task-worker-1 python $P logins
```

Two checks:

1. **Consistency** — the snapshot's `activity_24h.<metric>` equals the probe's **YESTERDAY** count.
2. **Windowing (live)** — do the action now (e.g. `uv run infrahubctl branch create test-$(date +%s)`,
   or log in at the UI), re-run the probe: **TODAY** and **LAST 3H** rise while **YESTERDAY** stays
   frozen. That is the guarantee — today's events never leak into yesterday's closed window.

Metrics accepted: `logins`, `branches_created` / `_merged` / `_deleted`, `checks_started` /
`_passed` / `_failed`, `artifacts_created` / `_updated`, and `webhooks` (success/failure).

## 5. Graceful degradation

`null` means a source failed (and was logged); `0` means it was measured with nothing to count. A
healthy run has no `null`s. To see a source degrade in isolation without breaking the rest, point
one metric's source at a failing dependency — only that field goes `null`.

## Caveats worth knowing

- **`checks_passed` / `checks_failed`** are only emitted for validators that run the checks
  runner. A trivial proposed change concludes its integrity validators without executing checks,
  so it produces `checks_started` only — `started` can exceed `passed + failed` with nothing
  actually incomplete. To move `passed`/`failed`, use a proposed change with real conflicts or a
  connected repository with checks.
- **`webhooks_fired_*`** counts `webhook-process` flow-runs. In a bare dev stack the
  event → automation delivery may not fire on its own; generate real webhook traffic (a webhook
  subscribed to `all` events plus a triggering mutation) to exercise it.

## The ad-hoc probe (`window_probe.py`)

The script lives beside this file. It evaluates the production windowed counters against a chosen
reference time, so you can confirm just-now activity is captured without waiting for the calendar
day to roll. Run it inside a worker container (which has the Prefect client and `PREFECT_API_URL`
configured); pass an `activity_24h` field name as the argument (defaults to `logins`).
