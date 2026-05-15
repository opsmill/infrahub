# Specification Quality Checklist: Enriched GraphQL Error Catalogue

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-13
**Last reviewed**: 2026-05-15
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
- [ ] All acceptance scenarios are defined — *US1 scenario 4 still needs to specify that each failing field carries its own sub-code (`ATTRIBUTE_REQUIRED` / `ATTRIBUTE_INVALID_TYPE` / `ATTRIBUTE_CONSTRAINT_VIOLATION`). Pending Q-D1.*
- [x] Edge cases are identified
- [x] Scope is clearly bounded — *Transport scope reaffirmed as GraphQL-only on the wire (2026-05-15). REST keeps current shape; OpenAPI long-term direction captured in the new Future Direction section. CI scope further narrowed (2026-05-15) to frontend bindings only — SDK lives in the `python_sdk/` submodule and its binding sync is enforced by the SDK repository's own CI.*
- [ ] Dependencies and assumptions identified — *Assumptions now reflect: GraphQL-only wire-format scope; shared Python catalogue; CI covers frontend bindings only (SDK external); cross-repo workflow uses the catalogue's machine-readable schema (FR-012) as the contract that crosses the repo boundary. Still missing FRs from discovery §9 (per-error explosion, `path` requirement, telemetry/logging, `data` evolution rules) — pending Q-D5.*

## Feature Readiness

- [ ] All functional requirements have clear acceptance criteria — *Current FRs are clear, including the new FR-015 `UNDEFINED_ERROR` requirement. Four additional FRs proposed in discovery §9 are pending Q-D5.*
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria — *SC-008 added (2026-05-15) for `extensions.code` always-present invariant on GraphQL responses.*
- [x] No implementation details leak into specification

## Pending decisions (block final sign-off)

These remain open in discovery §10:

- **Q-D1** — adopt the v1 catalogue (9 codes incl. auth split and validation split)?
- **Q-D4** — adopt the worked example shapes in §8 as canonical?
- **Q-D5** — promote the four "Belongs in the spec" items from discovery §9?

Resolved:

- **Q-D2** *(resolved 2026-05-15)*: REST keeps current wire format; the catalogue is GraphQL-only on the wire, with the Python catalogue shared across transports and OpenAPI as the long-term REST documentation surface.
- **Q-D3** *(partially applied 2026-05-15)*: Breaking Changes reframe, Transport assumption, `UNDEFINED_ERROR` (FR-015 + Edge Cases), SC-008, the new Future Direction section, and the CI-scope narrowing (FR-009/US4/SC-005/CI-scope assumption — frontend-only) are applied. Outstanding pieces gated on Q-D1 and Q-D5.

## Pending spec amendments (gated on remaining decisions)

Once Q-D1, Q-D4, and Q-D5 are answered:

1. **FR-005**: replace the analysis-driven phrasing with the agreed v1 list.
2. **US1 acceptance scenario 4**: tighten to require per-field sub-codes.
3. **Add new FRs** (Q-D5 default = all four):
   - Per-error explosion for bundled validation errors.
   - GraphQL `path` MUST point at the failing field for catalogued field-level errors.
   - Structured logs and telemetry include the catalogue `code`.
   - `data` schema evolution rules (additive non-breaking; remove/rename follows deprecation policy).
4. **Worked examples**: confirm the §8 shapes as canonical so generators target them (Q-D4).

## Notes

- All three of the original `[NEEDS CLARIFICATION]` markers (FR-005 initial scope, FR-011 HTTP-status placement, FR-012 discoverability format) were resolved on 2026-05-13.
- Discovery work (2026-05-13 → 2026-05-15) produced [discovery.md](../discovery.md): cross-transport error inventory, recommended v1 catalogue (9 codes), worked examples for `NODE_NOT_FOUND` and the `VALIDATION_ERROR` family, the boundary between Infrahub-validated errors and graphql-core-rejected errors, and the principle that `extensions.data` carries only what the consumer doesn't already know from their request.
- The 2026-05-15 reviewer feedback narrowed the wire-format scope to GraphQL only and added a Future Direction section pointing at OpenAPI as the long-term home for REST error documentation.
- A subsequent 2026-05-15 review further narrowed the CI scope: FR-009 covers frontend bindings only; the Python SDK (a git submodule = separate repo) has its own CI that consumes the catalogue's published machine-readable schema (FR-012) as an external input. The catalogue schema is therefore the cross-repo contract. US4 and SC-005 were tightened to match; a new US4 acceptance scenario 4 asserts the SDK submodule is not inspected by the in-repo CI.
- Both `spec.md` and `discovery.md` now carry a "Code-reference baseline: `76395fd1c`" header so any `file:line` references can be re-located against that commit if drift occurs before implementation lands.
- The spec uses GraphQL terminology (`errors`, `extensions`, `code`, `data`) because the feature is *defined* in those terms by the user and by INFP-468. This is treated as domain language, not as a leaked implementation detail.
- "Python SDK" and "TypeScript bindings" are referenced as concrete consumers (named in the user input); the spec stays implementation-agnostic about *how* those bindings are produced.
- Verified blast radius: 2 frontend files (`graphqlClientApollo.tsx`, `pages/login.tsx`), 0 SDK files. Both frontend sites read GraphQL-bound responses (auth-short-circuit case) so the migration sits within the GraphQL scope.
