# Alignment Check: spec.md vs source PRD (IFC-2704)

**Date**: 2026-07-10 · **Spec**: [spec.md](./spec.md)

## Source

- **Primary PRD**: the IFC-2704 epic body ("Make generator and artifact execution incremental
  on merge") — a substantive embedded PRD with where-it-happens, validated findings, proposed
  approach, open questions, testing focus, and related links. Fetched from Jira at the start of
  this run and used verbatim as the source-of-truth.
- **Referenced (not re-fetched)**: INFP-607 (JPD product idea the epic implements), and the
  local plan `dev/specs/ifc-2306-incremental-post-merge-recompute/plan.md` (predates
  fingerprints; the epic states its §2a/§3.1 findings were carried into the epic body itself).
  The epic body is self-contained, so these were not separately resolved.

## Verdict

✅ **ALIGNED** — every PRD requirement, constraint, and testing-focus item is represented in
`spec.md`; the additions are faithful derivations or plan-level mechanism, not scope creep or
semantic change.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|
| — | (none) | Selective execution on merge | FR-001, SC-001/002 | PRD's core intent; matched. |
| — | (none) | Capture pre-freeze, not post-merge | FR-002, Assumptions (diff capture point) | "Do not retrieve/recompute the diff after the merge" → FR-002; capture point recorded. |
| — | (none) | Don't source from changelog (conflict-to-base retained) | FR-003, Edge Cases | Matched exactly. |
| — | (none) | Fingerprint dissolves repo-code problem; API edits via node diff | FR-004, FR-006, Key Entities (Code fingerprint) | Both signals represented; fingerprint as an entity, not an FR (kept implementation-neutral). |
| — | (none) | Edit-then-revert → no regen | FR-005, SC-005 | Matched. |
| — | (none) | Over-execution acceptable, under-execution not | FR-010, SC-003, Overview | The INFP-409 invariant is stated as the guiding rule. |
| — | (none) | New-target / artifact `limit` trap | FR-007, Edge Cases | PRD's "Trap" → FR-007 + edge case (member filter, no under-execution on new targets). |
| — | (none) | Fallbacks all point at over-execution | FR-008 | Cache miss / diff-load failure / null fingerprint / incomplete closure enumerated. |
| — | (none) | Config flag (like `diff_update_after_merge`) | FR-012, Assumptions | Flag + reversible rollout; default-enabled mirrors the cited analog (which defaults True). |
| — | (none) | Direct-merge generator-output cascade (Open Q1) | FR-011, Edge Cases, Assumptions | Captured as a requirement + open design point flagged for the plan (resolved in research D7). |
| — | (none) | Merge path replaceable without affecting other callers | FR-013, Assumptions (scope) | PRD's "submitted nowhere else" → FR-013. |
| — | (none) | Both direct and PC merges | FR-009 | Matched. |
| — | (none) | Testing focus (6 items) | SC-001..005, quickstart matrix | All six PRD testing-focus items map to success criteria / quickstart scenarios. |
| info | added (faithful) | — | Plan/research: member reconciliation, observability metric | Not in the PRD as requirements; they are plan-level correctness mechanism (from the critique) and an operational recommendation. They do not alter any spec requirement, so no drift. |
| info | expansion | Open Q2/Q3 (repo ordering, fingerprint availability) | research D8/D6 | Resolved in the plan, not dropped; no spec-level requirement was needed. |

## Action

**Proceed.** No missing, contradicted, or semantically-changed requirements; no softened
acceptance criteria. Additions introduced during planning (member-level reconciliation,
observability, fallback hardening) are elaborations that strengthen the same requirements the
PRD states. `tasks.md` stands as generated. No remediation pass required (remediation counter
= 0).
