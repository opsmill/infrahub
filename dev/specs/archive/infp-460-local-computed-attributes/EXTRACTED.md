# Extraction Record

**Extracted on**: 2026-07-31
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- None. This spec has no `research.md`, so no decision records were extracted. The architectural
  decision it describes (inline evaluation for local changes, background tasks for remote) is
  recorded in `dev/adr/0011-inline-local-computed-attributes.md`, extracted from the sibling spec
  `ifc-2273-local-computation-jinja2`.

## Knowledge Updated

- None. The behavior is already documented in `dev/knowledge/backend/computed-attributes.md`: the
  inline local-update path (`_recompute_local_jinja2()`), the remote async path, the transform
  exclusion, and the four-path lifecycle summary.

## Guidelines Updated

- None.

## Archive

Spec directory moved to `specs/archive/infp-460-local-computed-attributes/` as a historical record.
