# Quickstart / Validation Guide: Phase 1 Telemetry Collection

How to validate the feature end-to-end. Implementation details live in `tasks.md`; this is a
run/verify guide.

## Prerequisites

```bash
uv sync --all-groups
export DOCKER_HOST=unix://$HOME/.docker/run/docker.sock   # component tests need the user docker socket
```

## 1. Unit: degradation helper (fast, no DB)

Validates `null`-on-failure vs `0`-on-empty in isolation (SC-001).

```bash
uv run pytest backend/tests/unit/telemetry/test_utils.py -q
```

Expected: a failing metric coroutine yields `None`; a succeeding-but-empty coroutine yields `0`.

## 2. Component: managed-node count exactness (SC-003)

```bash
uv run pytest backend/tests/component/telemetry/test_database.py -q
```

Expected: with a fixture of N managed nodes seeded via existing schema helpers,
`node_count["corenode"]` equals N exactly (±0), and `node_count["total"]` (raw vertices) is
unchanged and ≥ N.

## 3. Component: 24h windowing + activity metrics (SC-002)

```bash
uv run pytest backend/tests/component/telemetry/test_task_manager.py -q
```

Expected:
- `account.logged_in` events seeded inside the trailing 24h are counted; out-of-window events
  are not.
- `unique_logins` collapses multiple logins from the same account to one.
- `webhook-process` flow runs in-window split correctly into success/failure; the existing
  unwindowed `prefect.events.*` output is unchanged.

## 4. Component: full gather flow presence + degradation (SC-001)

```bash
uv run pytest backend/tests/component/telemetry/test_tasks.py -q
```

Expected:
- The gathered payload contains `accounts.{active,groups}`, `branches.active`,
  `database.node_count.corenode`, and `activity_24h.{logins,unique_logins,webhooks_fired_success,webhooks_fired_failure}`.
- When one source is made to fail (injected failing collaborator/fixture — no `unittest.mock`),
  that field is `null`, every other field is populated, and the payload is still built/stored.

## 5. Whole telemetry suite + lint

```bash
uv run pytest backend/tests/unit/telemetry backend/tests/component/telemetry -q
uv run invoke format lint
```

## 6. Manual payload inspection (optional)

Trigger the daily flow in a dev stack and inspect a stored snapshot to confirm
`payload_format == "20260628"` and the new fields are present with sensible values.

## 7. Governance gate (GR-001) — before merge/release

Confirm with the cloud-processor owner and the data-mart owner that the `payload_format` bump
and new fields are tolerated (consumer ignores unknown fields). Record the confirmation on the
PR / tracking ticket. No code change depends on it (additive), but it gates release.

## Success criteria mapping

| Criterion | Validated by |
|-----------|--------------|
| SC-001 (presence + null-vs-0) | Steps 1, 4 |
| SC-002 (exact 24h window) | Step 3 |
| SC-003 (corenode exact) | Step 2 |
| SC-004 (additive, format bump, consumer-safe) | Step 6 + Step 7 |
