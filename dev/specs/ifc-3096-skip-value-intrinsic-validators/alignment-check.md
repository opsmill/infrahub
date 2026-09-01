# Spec / Ask Alignment Check

**Feature**: IFC-3096 — Stop emitting value-intrinsic constraint validators on data-only diffs
**Date**: 2026-08-31
**Remediation passes used**: 0 of 2

## 1. Source

The source PRD is the **description field of [IFC-3096](https://opsmill.atlassian.net/browse/IFC-3096)**, retrieved via the Atlassian MCP connector at the start of this run and preserved verbatim in the session scratchpad. It is a full PRD — problem statement, 9 user stories, 2 prioritised journeys, 5 functional requirements, key entities, classification, 5 edge cases, 4 success criteria, implementation decisions, testing decisions, constitution alignment, governance gates, 3 assumptions, 4 out-of-scope items, 2 open questions, and further notes.

No secondary URLs were referenced by the ticket, so the ticket description is the sole source of truth.

## 2. Verdict

⚠️ **MINOR DRIFT (proceeding)**

Every PRD requirement, success criterion, edge case, assumption and out-of-scope item is present in `spec.md`. Three differences from the PRD are **deliberate factual corrections**, each verified against the code and each documented with its evidence. Two small gaps were found and fixed inline during this check. Nothing was dropped, softened, or silently rescoped.

The corrections matter enough to need action outside this repo: **the Jira ticket now contradicts the spec in three places** and should be updated so the two do not disagree for the next reader.

## 3. Findings

| Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|
| ⚠️ Corrected | changed | Success Criteria, SC-002: "total scheduled constraints fall by approximately 3K — the attribute-kind, attribute-optionality and relationship-peer triple currently scheduled unconditionally for every pair" | `spec.md` SC-002 | **The PRD's figure is arithmetically wrong.** The named triple cannot apply to a single (kind, field) pair — a pair is either an attribute or a relationship, never both. Verified against the determiner and the existing fixtures: an attribute pair schedules `kind`/`optional`/`unique` (2 of 3 value-intrinsic); a relationship pair schedules `peer`/`cardinality`/`optional`/`min_count`/`max_count` (1 of 5). Restated as `2A + R + P` with the derivation shown. SC-002 is marked "Gated in CI", so shipping the wrong formula would have produced a gate that either fails on correct behaviour or gets loosened until it asserts nothing. |
| ⚠️ Corrected | changed | Testing Decisions: "the determiner component test, covering ... the schema-diff producer still contributing at unrestricted scope when a guarded property genuinely changes" | `spec.md` FR-002 *Verify*; `plan.md` Step 5; `tasks.md` T014–T018 | **The PRD places the FR-002 check in a test that structurally cannot perform it.** The determiner component test exercises `ConstraintValidatorDeterminer.get_constraints` — the *data-diff* producer — which after this change contributes nothing for these constraints. A test placed there would pass while FR-002 was entirely broken. The schema-diff producer is `MergeSchemaAnalyzer::calculate_validations`, composed by `ConstraintInfoMerger::merge`; no test currently covers it at all. Rehomed to a new composition test plus one end-to-end case. |
| ⚠️ Corrected | changed | Testing Decisions: "Determiner component test (backend, component, extends): three assertions invert" | `research.md` R5; `tasks.md` T028–T033 | The actual count is **six edit sites**: two shared fixtures, a module-level `RELATIONSHIP_PROPERTIES` tuple, and three individual tests. Enumerated from the file. Does not change scope, but the task list must cover all six or the suite fails. |
| ℹ️ Clarified | changed | Key Entities / Implementation Decisions: "eight checkers change their declaration" | `research.md` R2; `spec.md` SC-001 | Eight *classes* is correct, but several are registered under multiple identifiers (`AttributeLengthChecker` covers four), so **fourteen constraint identifiers** stop being scheduled. Both figures are right at their own granularity; the spec now states both so the pinning test's expected literal is unambiguous. |
| ✅ Fixed inline | missing | User Story 9: "As a reviewer, I want the classification change to be visible as an explicit, reviewable list rather than diffuse logic, so that I can check each entry against its justification." | `spec.md` US3 acceptance scenario 4 | The PRD's ninth user story was delivered in substance (the Classification tables, and the pinning test's expected literal whose diff is the reviewable list) but had no acceptance criterion of its own. Added as US3 scenario 4 during this check. |
| ✅ Fixed inline | contradicted | Open Questions #2 | `spec.md` Open Questions | The spec still carried the rebase-hash-gate question as *pending planning confirmation* after `research.md` R3 had settled it. Stale within the doc set. Replaced with the resolution and its argument during this check. |
| ✅ Addition, justified | added | — | `spec.md` FR-006 | Promotes the PRD's stated Implementation Decision ("the default stays 'a data change can violate this'; flipping it was considered and rejected") into a testable requirement. Formalisation of a PRD decision, not new scope. |
| ✅ Addition, justified | added | — | `spec.md` Edge Cases (profile/template), Rollback section, SC-004 knowledge-page requirement | Three additions from the engineering critique: the profile/template asymmetry (where the PRD's general claim "the schema-diff producer picks it up" is *not* true), an explicit rollback trigger (absent from the PRD, and material for a change whose failure mode is invisible), and durable recording of the SC-004 measurement. None widens the implementation scope. |

### Not drift

Checked and confirmed present, unchanged in substance: all 5 PRD functional requirements; all 9 user stories (mapped onto 3 consolidated stories); both prioritised journeys; all 4 key entities; the full classification in both directions; all 5 original edge cases; SC-001, SC-003, SC-004; all 3 assumptions; all 4 out-of-scope items; both open questions; the governance-gate assessment; and the constitution alignment (plan.md covers the 5 principles the PRD names, plus III and VI).

## 4. Action

**Proceed.** No remediation pass required — no requirement is missing, softened, or contradicted, and the scope is unchanged from the PRD.

**One action outside this repository**, which this check cannot perform on its own:

> The Jira ticket IFC-3096 description now disagrees with the spec on (a) SC-002's reduction formula, (b) where the FR-002 test lives, and (c) the "three assertions invert" count. The ticket should be updated so a reader coming from Jira is not misled. Flagged for the ticket owner rather than edited automatically — amending a Jira description is an outward-facing change.
