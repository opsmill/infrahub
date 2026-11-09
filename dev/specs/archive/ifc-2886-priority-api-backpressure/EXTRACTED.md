# Extraction Record

**Extracted on**: 2026-07-26
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- `dev/adr/0008-client-declared-request-priority.md` (spec.md Assumptions + Governance Gates;
  shared with `ifc-2890-frontend-request-priority`)
- `dev/adr/0009-per-worker-coordination-free-admission.md` (R4, R8)

## Knowledge Updated

- `dev/knowledge/backend/api-backpressure.md` (The `Retry-After` hint — new; Metrics;
  Configuration; Why it's built this way — new, from R1/R2/R3/R6; The request path — excluded-path
  accuracy fix; Design record)

## Guidelines Updated

- `dev/guidelines/backend/testing.md` (Caution against mocking → Time: inject a clock, don't
  freeze one — from R7)
- `dev/guidelines/backend/python.md` (ASGI Middleware — new, from R1/R6)

## Not Extracted

- R5 (metrics module layout) — follows the existing `*/metrics.py` convention; already codified by
  precedent.
- `data-model.md`, `contracts/` — already captured in `dev/knowledge/backend/api-backpressure.md`
  and the generated configuration reference.
- `plan.md`, `tasks.md`, `quickstart.md`, `alignment-check.md`, `opsmill-implement-report.md`,
  `checklists/`, `critiques/` — execution artifacts.

## Archive

Spec directory moved to `specs/archive/ifc-2886-priority-api-backpressure/` as a historical
record.
