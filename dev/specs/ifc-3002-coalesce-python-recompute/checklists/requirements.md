# Specification Quality Checklist: Coalesce Python transform computed attributes on merge and rebase

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-11
**Last revised**: 2026-08-11 (iteration 3, after adversarial critique)
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
- [x] At least one success criterion can fail

## Requirement-to-scenario map

| Requirement | Covered by |
| --- | --- |
| FR-001 | US1 AS1 |
| FR-002 | US1 AS2 |
| FR-003 | US1 AS3 |
| FR-004 | US1 AS4 |
| FR-005 | US1 AS11, SC-004 |
| FR-006 | US1 AS11, verified by the parity task in tasks.md |
| FR-007 | US1 AS5, AS6 |
| FR-008 | US1 AS7 |
| FR-009 | US1 AS8 |
| FR-010 | US1 AS8 |
| FR-011 | US1 AS9 |
| FR-012 | US1 AS10 |
| FR-013 | US1 AS12 |
| FR-014 | US2 AS1, AS2 |
| FR-015 | US2 AS1, AS3 |
| FR-016 | US3 AS1 |
| FR-017 | US3 AS2, AS3, AS5 |
| FR-018 | US3 AS4, verified by the schema-failure task in tasks.md |
| FR-019 | US4 AS1 |
| FR-020 | US4 AS2 |
| FR-021 | US4 AS3 |

## Validation record

### Iteration 1

One item failed: **all functional requirements have clear acceptance criteria**. The requirement that ordinary user edits keep their behaviour had no scenario, which mattered because the feature works by making merge events stop matching the per-node automations, so breaking the live path is the likeliest regression. Fixed by adding a direct-edit scenario.

### Iteration 2 (during planning)

Phase 0 research reversed the deduplication direction for a schema-carrying merge. The original wording dropped the schema-driven refresh for pairs the coalesced pass covered; the two passes do not cover the same nodes, and that would have left untouched nodes stale.

### Iteration 3 (after adversarial critique)

Three independent reviewers examined the spec and plan. Ten findings were material and the specification changed substantially. The full report is in [../critiques/critique-20260811.md](../critiques/critique-20260811.md).

Two findings falsified requirements that had passed iterations 1 and 2:

- **The plan's owner-axis over-approximation violated FR-004 as it then stood.** Today's automation already filters on the transform's read fields; dropping the filter refreshes more nodes, not fewer. The specification now requires reproducing that filter on both axes, and SC-004 measures transform executions so the regression cannot hide behind a job count.
- **No success criterion could fail.** SC-001 was arithmetically unreachable because submissions are chunked, and nothing had a threshold that would stop the work. SC-001 is restated in terms of the chunk limit, and SC-007 is an explicit fail criterion with a number in it.

Structural changes: the deleted-peer work became its own user story, because it is a correctness bug that is independently valuable and also affects live deletes; the observability story gained the feature switch, because a code revert is not a rollback an operator can perform; and a requirement was added for waiting on schema convergence, closing a path where a stale worker registry silently drops the whole refresh.

A new checklist item was added — *at least one success criterion can fail* — because its absence was the finding that most nearly let a slower-than-baseline design ship.

Re-ran validation. All items pass.

## Notes

- Zero `[NEEDS CLARIFICATION]` markers.
- The Overview carries a "Context and constraints" subsection with six findings that shape the solution. It stays at the level of system behaviour and names no code symbol, file or class. It exists so the planning step does not rediscover them, and because two of the six were discovered only by adversarial review.
- SC-002 and SC-007 are expressed against a baseline that does not exist. Measuring it is the first phase of the plan, and the plan treats it as a go/no-go gate rather than a preparatory task.
