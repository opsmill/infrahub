# Extraction Record

**Extracted on**: 2026-07-31
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- `dev/adr/0012-selective-post-merge-regeneration.md` (from research.md D1, D2, D4, D6, D7, D9)

## Knowledge Updated

- None. The flow, selection (gate, member reconciliation, impact classifier), the
  generator-to-artifact cascade, the content-composition limitation, the fallback-reason table, and
  the shared `core/regeneration/` package are already documented in
  `dev/knowledge/backend/selective-merge-regeneration.md`, authored by this spec's implementation.

## Guidelines Updated

- `dev/guidelines/backend/python.md` (Exception Handling): added "Best-effort side effects degrade
  to a safe fallback", generalizing the best-effort merge-diff capture into a broad-catch rule.

## Archive

Spec directory moved to `specs/archive/ifc-2704-incremental-merge-regen/` as a historical record.
