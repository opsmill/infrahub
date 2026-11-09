# Extraction Record

**Extracted on**: 2026-07-26
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- `dev/adr/0008-client-declared-request-priority.md` (research.md Open question 1, incl. the
  critique P3 rejection of server-side origin inference; shared with
  `ifc-2886-priority-api-backpressure`)

## Knowledge Updated

- `dev/knowledge/frontend/request-priority.md` (header — ADR cross-link, archived spec path)

## Guidelines Updated

None. The transport-boundary convention is already stated prescriptively in
`dev/knowledge/frontend/request-priority.md`; a separate guideline would duplicate it.

## Not Extracted

- Open question 2 (empty `low` set in v1) — a scope decision, already recorded in the knowledge
  file.
- `contracts/`, `data-model.md` — already captured in the knowledge file.
- `plan.md`, `tasks.md`, `quickstart.md`, `alignment-check.md`, `opsmill-implement-report.md`,
  `checklists/`, `critiques/` — execution artifacts.

## Archive

Spec directory moved to `specs/archive/ifc-2890-frontend-request-priority/` as a historical
record.
