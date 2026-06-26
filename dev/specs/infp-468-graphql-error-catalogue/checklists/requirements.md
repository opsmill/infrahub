# Specification Quality Checklist: Enriched GraphQL Error Catalogue

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-13
**Last reviewed**: 2026-05-19
**Feature**: [spec.md](../spec.md)
**Companion**: [discovery.md](../discovery.md)
**Code-reference baseline (spec + discovery)**: `76395fd1c` (`stable` branch tip, 2026-05-13).

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
- [x] All acceptance scenarios are defined — *US1 scenario 4 tightened (2026-05-19) to require per-field sub-codes (`ATTRIBUTE_REQUIRED` / `ATTRIBUTE_INVALID_TYPE` / `ATTRIBUTE_CONSTRAINT_VIOLATION`).*
- [x] Edge cases are identified
- [x] Scope is clearly bounded — *Transport scope reaffirmed as GraphQL-only on the wire (2026-05-15). REST keeps current shape; OpenAPI long-term direction captured in the new Future Direction section. CI scope further narrowed (2026-05-15) to frontend bindings only — SDK lives in the `python_sdk/` submodule and its binding sync is enforced by the SDK repository's own CI.*
- [x] Dependencies and assumptions identified — *Assumptions reflect: GraphQL-only wire-format scope; shared Python catalogue; CI covers frontend bindings only (SDK external); cross-repo workflow uses the catalogue's machine-readable schema (FR-012) as the contract that crosses the repo boundary. Four FRs from discovery §9 added as FR-016 through FR-019 (2026-05-19).*

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — *FR-001 through FR-019 are clear and testable, including FR-015 (`UNDEFINED_ERROR`) and the four new FRs added 2026-05-19 (per-error explosion, `path` requirement, telemetry/logging, `data` evolution rules).*
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria — *SC-008 added (2026-05-15) for `extensions.code` always-present invariant on GraphQL responses.*
- [x] No implementation details leak into specification

## Decisions (all resolved)

- **Q-D1** *(resolved 2026-05-19)*: Adopt the 9-code v1 catalogue with both proposed splits (auth split: `AUTHENTICATION_REQUIRED` + `TOKEN_EXPIRED`; validation split: `ATTRIBUTE_REQUIRED` / `ATTRIBUTE_INVALID_TYPE` / `ATTRIBUTE_CONSTRAINT_VIOLATION`). Applied to FR-005 and US1 scenarios 3 + 4.
- **Q-D2** *(resolved 2026-05-15)*: REST keeps current wire format; the catalogue is GraphQL-only on the wire, with the Python catalogue shared across transports and OpenAPI as the long-term REST documentation surface.
- **Q-D3** *(resolved 2026-05-19)*: All listed spec updates applied — Breaking Changes reframe, Transport assumption, `UNDEFINED_ERROR` (FR-015 + Edge Cases), SC-008, Future Direction section, CI-scope narrowing (FR-009/US4/SC-005), FR-005 final list, US1 sub-code tightening, and the four FRs from Q-D5.
- **Q-D4** *(resolved 2026-05-19)*: Adopt the discovery §8 worked-example shapes as canonical reference (`NODE_NOT_FOUND`: `{node_kind, identifier}`; `ATTRIBUTE_REQUIRED`: `{node_kind, field_name}`; `ATTRIBUTE_INVALID_TYPE`: `{node_kind, field_name, expected_type, received_type}`). Field names may still be refined during planning.
- **Q-D5** *(resolved 2026-05-19)*: All four "Belongs in the spec" items promoted from discovery §9 — added to spec.md as FR-016 (per-error explosion), FR-017 (`path` requirement), FR-018 (telemetry/logging), FR-019 (`data` evolution rules).

## Notes

- All three of the original `[NEEDS CLARIFICATION]` markers (FR-005 initial scope, FR-011 HTTP-status placement, FR-012 discoverability format) were resolved on 2026-05-13.
- Discovery work (2026-05-13 → 2026-05-15) produced [discovery.md](../discovery.md): cross-transport error inventory, recommended v1 catalogue (9 codes), worked examples for `NODE_NOT_FOUND` and the `VALIDATION_ERROR` family, the boundary between Infrahub-validated errors and graphql-core-rejected errors, and the principle that `extensions.data` carries only what the consumer doesn't already know from their request.
- The 2026-05-15 reviewer feedback narrowed the wire-format scope to GraphQL only and added a Future Direction section pointing at OpenAPI as the long-term home for REST error documentation.
- A subsequent 2026-05-15 review further narrowed the CI scope: FR-009 covers frontend bindings only; the Python SDK (a git submodule = separate repo) has its own CI that consumes the catalogue's published machine-readable schema (FR-012) as an external input. The catalogue schema is therefore the cross-repo contract. US4 and SC-005 were tightened to match; a new US4 acceptance scenario 4 asserts the SDK submodule is not inspected by the in-repo CI.
- Both `spec.md` and `discovery.md` now carry a "Code-reference baseline: `76395fd1c`" header so any `file:line` references can be re-located against that commit if drift occurs before implementation lands.
- The spec uses GraphQL terminology (`errors`, `extensions`, `code`, `data`) because the feature is *defined* in those terms by the user and by INFP-468. This is treated as domain language, not as a leaked implementation detail.
- "Python SDK" and "TypeScript bindings" are referenced as concrete consumers (named in the user input); the spec stays implementation-agnostic about *how* those bindings are produced.
- Verified blast radius: 2 frontend files (`graphqlClientApollo.tsx`, `pages/login.tsx`), 0 SDK files. Both frontend sites read GraphQL-bound responses (auth-short-circuit case) so the migration sits within the GraphQL scope.
