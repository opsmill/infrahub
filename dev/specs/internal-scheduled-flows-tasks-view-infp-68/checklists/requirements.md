# Specification Quality Checklist: Internal & Scheduled Background Flows in the Tasks View

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-24
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- The **Overview → Verified current behaviour** and **Dependencies** sections
  cite concrete files and line numbers. This is deliberate and is not a
  requirements leak: the feature request contained stale code references and the
  task explicitly asked for them to be re-verified against `origin/develop`. The
  requirements (FR-*) and success criteria (SC-*) themselves stay behavioural
  and name no file, framework or API shape.
- Every autonomous decision is recorded in **Assumptions** with its rationale,
  per the pipeline rule that no human answers clarification questions.
- A clarification pass ran on 2026-09-24 and self-answered five questions
  (parameter exposure, summary aggregation cost, refresh behaviour, scheduled-view
  scope, colour-independent status). They are logged under **Clarifications** and
  integrated as FR-009a, FR-012a, FR-013a, FR-016a, FR-019a, SC-006, SC-010,
  SC-011 and Assumptions 14–17.
- Assumption 3 (no new permission gates viewing) is explicitly flagged for
  reviewer attention — it is the one decision where a reasonable reviewer could
  land differently, and the spec names the narrower alternative. The
  clarification pass tested the premise against the catalogue rather than
  assuming it: the payload-bearing `webhook-send` workflow is already `CORE` and
  already visible with masking, so internal runs add no new class of sensitive
  data.
- Two factual corrections to the feature request are carried into the spec:
  19 internal workflows (not 16) and 5 scheduled flows (not 4 — `merge-watcher`
  was missing), which raises the volume estimate from ~2,880 to ~4,320 runs/day.
- A third correction was added in review round 1, this one to the request's root
  cause. Internal flows are *not* structurally excluded from the Tasks view:
  `add_tags()` adds the namespace tag by default, and eight internal workflows
  call it, so their runs already appear in the default list. The Overview now
  separates deployment-level type tagging from run-time namespace tagging,
  FR-003 defines the default by observed result rather than by workflow type,
  and Assumption 18 records the decision to leave those eight where they are.
- FR-004 was rewritten. Its earlier form ("a run with the namespace tag but no
  workflow-type tag stays visible by default") was unsatisfiable alongside
  FR-002: Prefect 3.8.6's `FlowRunFilterTags` offers no "lacks tag X" predicate.
  It now pins the deliberate asymmetry between the default selection and an
  explicit all-types selection. Assumption 19 records how the ticket's fifth
  acceptance criterion is satisfied without it.
