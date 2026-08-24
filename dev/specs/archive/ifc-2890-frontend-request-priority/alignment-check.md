# Spec/Ask Alignment Check: Frontend Request Prioritization (`X-Priority`)

**Date**: 2026-07-14
**Feature dir**: `specs/ifc-2890-frontend-request-priority/`
**Verdict**: ✅ ALIGNED

## Source

- **Source PRD**: [IFC-2890](https://opsmill.atlassian.net/browse/IFC-2890) — "Frontend request prioritization via `X-Priority` header." The ticket description is a full, structured PRD (problem statement, 7 user stories, 3 prioritised journeys, 7 functional requirements, key entities, edge cases, 4 success criteria, implementation/testing decisions, governance gates, assumptions, out-of-scope, 2 open questions).
- **Resolution**: fetched via the Atlassian MCP (`getJiraIssue`, markdown format) — the Jira URL is auth-gated, so `WebFetch` would not resolve it; the MCP fetch succeeded and returned the complete description.
- **Compared against**: the current `spec.md` (post-critique).

## Findings

Comparing the source PRD to `spec.md` for **significant** drift (missing / added-not-necessary / semantically changed / dropped-softened / contradicted). Cosmetic and expansion-of-detail differences are not drift.

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| ✅ none | missing | FR-001…FR-007 | spec FR-001…FR-007 | All seven functional requirements carried over verbatim, including the per-transport `Verify` clauses. |
| ✅ none | missing | 7 user stories | spec User Stories 1–6 | All 7 PRD stories represented. PRD US1 ("stay responsive") + US2 ("`high` by default, 89 sites") are consolidated into spec Story 1; PRD US3→Story 2, US4→Story 3, US5→Story 6, US6→Story 4, US7→Story 5. Consolidation, not omission. |
| ✅ none | dropped/softened | SC-001…SC-004 | spec SC-001…SC-004 | All four success criteria carried verbatim, including SC-004's explicit "joint / not a v1 blocker" framing — not softened beyond what the PRD itself states. |
| ✅ none | changed | Journeys P1–P3, Key Entities, Edge Cases, Governance Gates, Out of Scope | corresponding spec sections | Semantics preserved. Governance CORS "Ask First" gate and cooperative-trust assumption retained. |
| ✅ none | resolved | 2 Open Questions | spec Assumptions | Both PRD open questions resolved exactly as the prep input directed (unified `low` opt-in helper; possibly-empty initial `low` set) and recorded in Assumptions — the PRD explicitly deferred these "to the spec/plan step." |
| ℹ️ info (not drift) | added | — | spec Assumption on SC-001 measurement | Clarifies *how* SC-001 is validated given the backend counter is unlabeled (research §10). A necessary clarification of an existing PRD criterion, not new scope. |
| ℹ️ info (not drift) | added | FR-003 | spec Edge Case "invalid/unknown opt-in value" | Restates/defends FR-003 ("never emit anything but `high`/`low`"). A necessary clarification, not a new requirement. |
| ℹ️ info (not drift) | added | PRD Implementation Decisions ("No … GraphQL schema change") | spec Out of Scope "no GraphQL schema change" | Already stated in the PRD; making it explicit in Out of Scope is faithful, not additive. |

### Note on plan/tasks refinements (outside this spec.md comparison)

The critique introduced three risk-driven refinements that live in `plan.md` / `contracts/` / `tasks.md`, **not** in `spec.md`, so they do not affect spec↔PRD alignment:

- Per-transport value normalization to the `high`/`low` union (strengthens FR-003).
- Origin-based (not substring) external-host guard (refines FR-007's implementation).
- CORS `OPTIONS` preflight must not be shed by the outermost admission middleware (ensures FR-006 / Story 5 acceptance — "the request succeeds" — actually holds under the feature's own load premise). Scoped as a verify-first task (exempt-or-fix, record finding), not a mandated new build.

These strengthen the delivery of existing PRD requirements; none adds user-facing scope or reverses a PRD decision.

## Action

**Proceed.** `spec.md` faithfully reflects the IFC-2890 PRD: every requirement, story, journey, success criterion, entity, edge case, governance gate, assumption, and out-of-scope item is present with preserved semantics, and the two open questions were resolved as directed. The additions are necessary clarifications or implementation-layer refinements. No remediation pass required.
