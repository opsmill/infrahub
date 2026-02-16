# Quickstart: Local Telemetry Storage

**Feature**: `fac-001-local-telemetry-storage` | **Date**: 2026-02-16

## What This Feature Does

Infrahub now stores a daily telemetry snapshot locally in the database, regardless of whether remote telemetry reporting is enabled. This ensures all deployments — including air-gapped and opted-out — retain usage data for support, auditing, and license compliance.

## Key Changes

1. **Automatic daily storage**: The daily telemetry workflow now always stores a snapshot locally before optionally sending to the remote endpoint.
2. **CLI export**: `infrahubctl telemetry export` exports snapshots to a JSON file.
3. **CLI listing**: `infrahubctl telemetry list` shows a summary table of stored snapshots.
4. **REST API**: `GET /api/telemetry/snapshots` provides programmatic access.
5. **Permission**: Access requires `READ_TELEMETRY` global permission.

## Getting Started

### Verify Telemetry Storage

After the daily collection runs (or after triggering it manually), verify snapshots are stored:

```bash
infrahubctl telemetry list
```

### Export Telemetry Data

Export all snapshots to a JSON file:

```bash
infrahubctl telemetry export --output my-telemetry.json
```

Export snapshots from a specific date range:

```bash
infrahubctl telemetry export \
  --start-date 2025-11-01 \
  --end-date 2026-02-16 \
  --output last-90-days.json
```

### Grant Access

Assign the `READ_TELEMETRY` permission to a role via the Infrahub UI or API. Users with `SUPER_ADMIN` permission already have access.

## Architecture Overview

```
Daily Workflow (2 AM)
        │
        ▼
gather_anonymous_telemetry_data()
        │
        ├──► TelemetrySnapshot.save(db)  ← Always runs
        │
        ▼
  (opt-out check)
   ┌────┴────┐
   │         │
 opted-out  opted-in
   │         │
   ▼         ▼
 skip     POST to remote
 update    update status
 status    ("sent"/"failed")
 ("skipped")
```

## Files Modified/Added

| File | Change |
|------|--------|
| `backend/infrahub/telemetry/snapshot.py` | New — `TelemetrySnapshot` StandardNode model |
| `backend/infrahub/telemetry/tasks.py` | Modified — Always store locally, conditionally send remotely |
| `backend/infrahub/core/constants/__init__.py` | Modified — Add `READ_TELEMETRY` to `GlobalPermissions` |
| `backend/infrahub/permissions/constants.py` | Modified — Add denial message and description |
| `backend/infrahub/api/telemetry.py` | New — REST endpoint for snapshot retrieval |
| `backend/infrahub/api/__init__.py` | Modified — Register telemetry router |
| `python_sdk/infrahub_sdk/ctl/telemetry.py` | New — CLI commands (export, list) |
| `python_sdk/infrahub_sdk/ctl/cli_commands.py` | Modified — Register telemetry sub-app |
