# Extraction Record

**Extracted on**: 2026-07-26
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- `dev/adr/0010-generated-user-facing-schema-contract.md` (from research.md D2, D3, D5, plus the
  review of the implementing pull request)

## Knowledge Updated

- `dev/knowledge/backend/schema-definitions.md` (Field Visibility and the Write / Read / Internal
  Models — added generated enum classes for closed-set fields and the required `version` on the
  write root; See Also)
- `dev/knowledge/backend/code-generation.md` (Generation Pipeline — added the generated SDK schema
  models; When to Regenerate — visibility changes and the submodule commit, and the correct
  command for REST types; Validation — corrected the claim that submodule output is not validated;
  See Also)

## Guidelines Updated

None. The prescriptive rules this feature implies — classify a new field's `visibility`,
regenerate, commit the generated artifact — are already carried by
`dev/knowledge/backend/schema-definitions.md` and the "Generated Files" section of `AGENTS.md`.

## Not extracted

`research.md` is a Phase 0 document and three of its decisions were reversed while the feature was
implemented and reviewed: D3 (reject non-write fields → tolerate and drop them), D6 (round-trips
break → round-trips work), and D4's rendering choice (`Literal[...]` → dedicated enum classes).
`contracts/schema-models.md` and `opsmill-implement-report.md` carry the same superseded claims.
They are left unedited as a record of what was believed at the time; ADR 0010 documents the
decisions as they actually shipped and records the reversal as a rejected alternative.

The follow-ups in `opsmill-implement-followups.md` were still open at extraction time — retiring
the SDK's hand-written schema models, extracting schema code generation off the attribute
definition model, and publishing the write contract in the REST OpenAPI.

## Archive

Spec directory moved to `dev/specs/archive/002-user-facing-schema/` as a historical record.
