# Specification Quality Checklist: Repository branches card and branch-scoped details

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-10
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

Validated in one iteration. No frameworks, libraries, file paths or component names appear in the
User Scenarios, Functional Requirements or Success Criteria sections. Two deliberate exceptions,
both judged correct rather than leakage:

- **Contract vocabulary is named where a requirement is about the contract.** FR-016 names the three
  backend arguments the preview resolver rejects (`sync_status__value`, `internal_status__value`,
  own-values-only) because the requirement *is* "do not send these". Naming them is what makes the
  requirement testable; paraphrasing them would make it unverifiable. The same applies to
  `sync_status`, `CoreRepository` and `CoreReadOnlyRepository`, which are domain terms in this
  product, not implementation choices.
- **Technical constraints live in Assumptions and Dependencies, not in requirements.** The schema
  overlay, the absence of a pull request and the preview window's fabricated values are recorded
  where they belong — as context a planner needs — and no functional requirement depends on them.

No [NEEDS CLARIFICATION] markers were needed. Every question the research phase raised was settled
at a human checkpoint before this spec was written, and the four binding decisions are restated as
requirements (FR-005, FR-006, FR-016, FR-020) so they cannot be quietly reopened during planning.

One requirement is a regression guard rather than new behaviour — FR-017, that the paging
component's three existing call sites keep behaving exactly as today. It is stated as a requirement
because the paging change is a generalisation of a shared component, and that is the failure this
feature is most likely to cause elsewhere.
