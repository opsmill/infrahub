# Specification Quality Checklist: Rename the misleading `has_schema_changes` branch field

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-30
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

- The API field names (`has_schema_changes`, `schema_differs_from_default_branch`)
  appear throughout the spec. These are treated as the user-facing API contract
  being changed, not as implementation detail - the entire feature is a rename of
  a publicly queryable field, so the names are the subject matter.
- Two decisions that were open in INFP-469 are resolved and recorded: the final
  name (`schema_differs_from_default_branch`, chosen over the `has_schema_diverged`
  alternative for naming its reference point - see the Overview) and the removal
  version (1.14.0).
- SDK scope is explicitly excluded (OOS-001) and routed to a follow-up ticket, per
  the decision to avoid coupling the SDK to the latest Infrahub release. A second
  follow-up (OOS-005) tracks the actual 1.14.0 removal. Both follow-up tickets are
  required to exist before this feature is considered done.
- A few code-level references (the `Branch` vs `InfrahubBranch` GraphQL types, the
  backend model property, the unrelated `SchemaAnalyzer.has_schema_changes()`
  method, SDK file paths) appear in the requirements and scope sections. These are
  present deliberately as scoping guardrails - to state which of several
  identically named things are in and out of scope - not as design of the
  implementation. Without them an implementer could rename the wrong symbol or
  miss one of the two GraphQL representations.
- The UI copy is changed, not merely re-pointed: the current "schema updated" /
  "Has schema changes" wording is misleading in the same way the field name is, so
  FR-006 requires clearer wording that still fits the existing badge/label layout.
