# Spec/Ask Alignment Check: User-Facing Schema Separation

**Date**: 2026-07-01 | **Feature**: `specs/002-user-facing-schema`

## Source

Source-of-truth PRD (local files at repo root, no URLs):
- `PRD-user-facing-schema-separation.md`
- `schema-field-classification.md` (resolved per-field write/read/internal mapping)

Compared against `specs/002-user-facing-schema/spec.md`.

## Verdict

⚠️ **MINOR DRIFT (proceeding)** — every PRD requirement, success criterion, journey,
out-of-scope item, and governance gate is faithfully represented. The spec *adds* a
handful of requirements, all of which are justified clarifications or
constitution-mandated governance (not scope creep, and nothing dropped, softened, or
contradicted). Safe to proceed to implementation planning review.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| ✅ none | mapping | FR-001..FR-008 | FR-001, FR-002, FR-003, FR-004, FR-006, FR-007, FR-008, FR-009 | All eight PRD functional requirements are present (renumbered; PRD FR-005 → spec FR-006). |
| info | added (justified) | — | FR-005 (out-of-enum rejection) | Necessary clarification derived from PRD SC-002 (enum completeness) — makes the enum contract testable at the boundary. |
| info | added (justified) | Edge case "reading back a previously-stored schema" | FR-010 | Promotes a PRD edge case to a testable requirement. |
| info | added (governance) | Governance: "API change… ask first" + constitution changelog gate | FR-011 (changelog + upgrade note) | Added by critique M1; constitution mandates a changelog for user-facing changes and this is a breaking change. Justified, not scope creep. |
| info | added (justified) | FR-006 ("importable with only the SDK installed") | FR-012 (SDK models committed/shipped) | Added by critique M2; FR-006 is only true if the generated models ship in the SDK package. Makes an existing PRD requirement actually satisfiable. |
| info | added (justified) | PRD SC-001..005 | SC-006 (no regression) | Expansion guarding backward compatibility (PRD edge cases imply it). |
| info | changed (faithful) | PRD user stories #3/#4 (human author) | US3 (P2 journey) | The human-author value in the PRD user-story list is promoted to a P2 journey; content preserved. |
| info | added (justified) | Governance (API change) + critique R1/R2 | "Dependencies & Governance" notes on server/SDK release compat and `id`-driven-mutation authz | Operational/security clarifications from the critique; consistent with PRD scope. |
| ✅ none | out of scope | Export endpoint; kind-conditional read_only defaults; schema-visualizer | Out of Scope | All three PRD non-goals carried verbatim. |
| ✅ none | field mapping | schema-field-classification.md | "Field visibility model" + data-model.md | The resolved ⚠ decisions (state=write, hierarchy/hierarchical=read, identifier=write, id=write, node back-ref=internal) match the classification doc. |
| 🤔 open | success metric | PRD open question (SC-004 target) | SC-004 + Open Questions | Carried forward unchanged; product input pending. Non-blocking. |

## Action

**Proceed.** No missing PRD requirements, none dropped/softened/contradicted. The
additions are justified clarifications and constitution-mandated governance. No
remediation pass required (remediation counter: 0).
