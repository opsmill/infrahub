# Extraction Record

**Extracted on**: 2026-10-08
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- `dev/adr/0021-resource-allocation-telemetry.md` (D2–D7, D11–D17, combined into one ADR)

## Knowledge Updated

- `dev/knowledge/backend/telemetry.md` (CPU and memory figures: what an empty figure means, what
  cannot be seen from inside a container, the caveats of the per-worker share)
- `dev/knowledge/backend/async-tasks.md` (The worker liveness heartbeat runs on its own thread: the
  beat also carries the resource reading)

## Guidelines Updated

- `dev/guidelines/backend/checklist.md` (Telemetry — new: does this feature change the telemetry
  payload?)

## Not Extracted

- D1 (`psutil` becomes a runtime dependency) — a one-off, recorded in `pyproject.toml`.
- D8, D9, D10, D15 — superseded or reversed; recorded as rejected alternatives in ADR 0021.
- `data-model.md`, `contracts/` — covered by ADR 0021 and `dev/knowledge/backend/telemetry.md`; the
  contract stays here as the reference for the receiving service.
- The real-kernel test harness (`test_cgroup_kernels.py`) — too specific to this feature to be a
  general testing guideline.
- `plan.md`, `tasks.md`, `quickstart.md`, `checklists/`, `critiques/`, `alignment-check.md`,
  `opsmill-implement-report.md` — execution artifacts.

## Archive

Not moved yet. The directory is to be moved to `specs/archive/infp-631-resource-telemetry/` later;
the ADR's source path already points there, and the payload contract link in
`dev/knowledge/backend/telemetry.md` must be updated when it moves.
