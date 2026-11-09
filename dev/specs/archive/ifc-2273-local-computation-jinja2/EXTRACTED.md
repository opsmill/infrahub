# Extraction Record

**Extracted on**: 2026-07-31
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- `dev/adr/0011-inline-local-computed-attributes.md` (from research.md R1, R3, R5)

## Knowledge Updated

- None. `dev/knowledge/backend/computed-attributes.md` already documents this feature end to end
  (the four evaluation paths, `_recompute_local_jinja2()`, the `targets_self` neutralization,
  `_collect_extra_filters()` peer loading, and `get_local_jinja2_targets()`); it was authored by
  this spec's own implementation. No additions were needed.

## Guidelines Updated

- None. The relevant conventions (exception handling, `TYPE_CHECKING` deferral of `SchemaBranch`)
  are already present in `dev/guidelines/backend/python.md`.

## Archive

Spec directory moved to `specs/archive/ifc-2273-local-computation-jinja2/` as a historical record.
