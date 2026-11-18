# Specification Quality Checklist: Resource-pool form fields — value-or-pool tabs and target-kind override

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-07
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

Two iterations were applied before this checklist passed.

**Iteration 1 — implementation detail leaked into the spec.** The first draft named
components, files and props (`PoolSelect`, `field.pool`, `${name}.value.from_pool.*`,
`getFieldDefaultValue.ts`) throughout the requirements, and framed FR-006/FR-007 in terms of
React state. Rewritten in user-facing terms: "a field that can be satisfied from a pool",
"an untyped side channel", "where the existing value actually came from". The structural
detail belongs in plan.md, and is preserved in the scratchpad research documents.

**Iteration 2 — success criteria were technical.** Originally included "betterer stays at 186",
"`biome ci` exits 0" and "all five call sites migrated". Replaced with outcome statements
(SC-002 sampling finds no field on the old presentation; SC-008 no regression in existing
gates). The specific gate commands are a plan/task concern.

**Deliberate scope decisions recorded rather than clarified** (no [NEEDS CLARIFICATION]
markers were warranted, since each has a defensible default already agreed with the user):

1. Pool *availability* per field is unchanged — presentation only. Removes the create-only
   attribute asymmetry from scope.
2. Object-template overrides excluded (IFC-3135); a template has nowhere to store one.
3. Tightening the previously-unvalidated prefix-pool kind input is accepted as a behaviour
   change, on the grounds that the path had no coverage and could not produce a usable object.

**Known risk carried into planning**: FR-017 (correct mode on first render) depends on value
provenance being reported accurately. Existing behaviour can report a pool-allocated value as
user-provided; harmless while the pool was a button, but under an explicit two-way choice it
misinforms. The plan must either fix that or explicitly document the residual case.
