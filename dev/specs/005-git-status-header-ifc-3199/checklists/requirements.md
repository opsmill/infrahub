# Specification Quality Checklist: Git status indicator in the app header

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-15
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

Validation ran in two iterations.

**Iteration 1 — three items failed:**

1. *No implementation details* — the Functional Requirements named the component file, the
   design-system controls and the GraphQL field. Fixed: FR-001..FR-013 were rewritten to
   state observable behaviour only. The technical decisions were not discarded — they moved
   to "Technical constraints established by research" under Assumptions, which is where the
   template intends dependencies and established constraints to live. They are binding on
   the plan without pretending to be user-facing requirements.
2. *Success criteria are technology-agnostic* — an earlier SC cited the 10-second poll
   interval and a GraphQL count. Fixed: SC-003 now reads "within one refresh interval", and
   SC-006 states cost does not grow with repository count. The 10-second figure survives as
   a documented assumption, not as a success measure.
3. *Edge cases identified* — the first draft covered only the failure and empty cases. Added:
   lookup-failure, first-load, branch-change-in-flight, repository-added-to-empty-branch,
   all-repositories-failed, insufficient permission, and many-repositories.

**Iteration 2 — all items pass.**

No [NEEDS CLARIFICATION] markers were emitted. The two decisions that would have warranted
them — the empty-state treatment and the base branch — were put to the user before the spec
was written and are recorded under "Decisions already taken".

**Two items deliberately carried into planning rather than resolved here:**

- The partial-match behaviour of attribute-value filters is correct for the error value
  today but only incidentally. The spec obliges the plan to confirm or avoid it. This is a
  technical question with no user-facing reading, so it does not belong in the spec.
- Principle IV requires an E2E test for user-facing features, and `app-header.tsx` has no
  test of any kind today. The scale of that addition is a planning question.
