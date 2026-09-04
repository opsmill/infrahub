# Specification Quality Checklist: Re-enable ruff TRY400 so error logs carry tracebacks

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-11
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

**Note on the first two items**: this is a lint/tooling feature, so its "user" is an Infrahub
developer and its subject matter is inherently the lint configuration. Naming ruff, TRY400 and
`pyproject.toml` is describing *what* the change is, not leaking a chosen implementation. The
spec still avoids prescribing per-site edits — those belong to plan/tasks.

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

- Scope was narrowed from the source card (INBOX-29 named TRY004 **and** TRY400) to TRY400 only.
  The spec documents this in "Out of Scope — TRY004" with the reason: TRY004's fix changes
  caller-visible exception types on schema and GraphQL surfaces, which needs human design review.
  This is an intentional, recorded scope reduction, not drift.
- Violation counts in the spec were measured on this branch rather than taken from the card
  (card said ~56; actual is 76 = 36 TRY400 + 40 TRY004).
- FR-006's auth.py carve-out is a pipeline-permission boundary. The spec's Assumptions section
  records that the merged BLE precedent edited the same file, so a reviewer can overrule it.
