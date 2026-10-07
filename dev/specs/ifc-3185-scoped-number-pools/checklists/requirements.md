# Specification Quality Checklist: Scoped number pools — one pool serves every scope

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-02
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — field names (`allocation_scope`, `parameters.allocation_scope`, `from_pool`, the three dedicated query names and their fields) appear only where they are the user-facing contract; the Delivery order section names seams by role, not by module
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — the PRD's three open questions are resolved in Assumptions (three root query fields dedicated to number pools; any required scalar attribute may be an entry; the occupancy threshold is SC-006's output); the one open point (form A versus form B) is recorded for the final review, not left as a marker
- [x] Requirements are testable and unambiguous — every FR names the user story and scenario that verifies it
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded (P3 only; frontend, SDK helpers, search, new mutations, stored key, per-division lock, record moves, any change to the generic queries listed as out of scope)
- [x] Dependencies and assumptions identified (P1 landed in part, P2 foundational work landed, attach in flight gating only User Story 7, mocks accepted on the feature branch)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Source: `SCOPED-POOLS-PRD.md` (precedence 1), the Confluence revised PRD (2), the base PRD INFP-308 (3). Epic IFC-3185. Plus the frontend needs supplied on 2026-10-06 and the grilling decisions of the same day, which define the GraphQL surface.
- The user's delivery constraint (contract first, then seams, then internals, then mock removal) is recorded as a Delivery order section, User Story 1, FR-018, FR-019, SC-007, SC-010 and SC-011 so the plan and tasks phases inherit it and the alignment check can see it.
- Decisions taken autonomously and flagged in Assumptions: per-range rows on a scoped pool are computed over the fullest division within the range (FR-017); a schema-declared scope reconciles onto the pool from the default branch only, as P1 does for ranges; list and JSON attribute kinds are refused as scope entries; the dedicated surface uses flat lists rather than `edges { node }` wrapping.
