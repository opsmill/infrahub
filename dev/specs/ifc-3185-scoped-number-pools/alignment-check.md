# Spec / ask alignment check: Scoped number pools

**Date**: 2026-10-06 | **Spec**: [spec.md](./spec.md) | **Remediation passes used**: 0

## Source

- `SCOPED-POOLS-PRD.md` at the repository root (the P3 PRD, grilled 2026-10-01), read in full.
- The user's delivery constraint given with the ask: publish the GraphQL surface first (mock data
  where the real reads do not exist yet), then the utilization and allocation seams, then the
  internals; internal schema changes may need to come first; goal is to unblock the frontend as
  early as possible and allow the remaining work to be split and done concurrently.
- The frontend team's needs for the number pool screens, notes supplied by the user on 2026-10-06
  (ranges with figures, per-division utilization with branch split, divisions per range, allocated
  rows with holder and provenance, no pagination on divisions, no search), recorded in the spec's
  Input.
- The grilling session of 2026-10-06 on the GraphQL surface: generic queries frozen for number
  pools, a dedicated surface of three root fields, the division filter, the allocation row, the
  figures block, the divisions query, no new mutation, mocks allowed at contract time, "division"
  as the one word for the value tuple.
- The two Confluence PRDs the P3 PRD cites were not fetched: the P3 PRD states that it wins where
  they differ and that anything it does not mention stands as written there. The spec repeats that
  precedence.

## Verdict

Verdict: ⚠️ MINOR DRIFT (proceeding)

Every PRD functional requirement, success criterion, user story, journey, key entity, edge case and
out-of-scope item is present in the spec with the same number or an explicit mapping. The user's
delivery constraint is carried as a Delivery order section, User Story 1, FR-018, FR-019, SC-007,
SC-010 and SC-011. The GraphQL surface comes from the frontend needs and the grilling decisions,
which the PRD does not cover beyond asking for the per-division read to be agreed before
implementation. The deltas below are additions and clarifications the PRD invited or the code
forced, except two changes the user made to the PRD's FR-011 on 2026-10-07: the divisions listing
holds only the divisions holding a value, and no figure reports the fullest division by default.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|
| Minor | added | Open question 1 (shape of per-division utilization) | FR-015, FR-016, FR-022, FR-026, Assumptions, the contract | Resolved to three root query fields dedicated to number pools, with a defined division entry (path, value, display label, peer kind, identifier fallback) and one figures block with absolute counts. The PRD asked for this contract to be agreed before implementation; the frontend needs and the grilling decided its shape. |
| Minor | added | — (grilling decision 1) | FR-028, FR-029, SC-009 | The generic resource-pool queries are frozen for number pools and gain a description note; P2's provenance moves to the dedicated surface. The PRD says nothing about the generic queries. |
| Minor | added | — (grilling decisions 3 and 4) | FR-023, FR-024, FR-025 | The allocation list with its row shape, filters, refusals and the cross-branch overlap of divisions. The PRD covers allocation and utilization, not a listing of tracked numbers. |
| Minor | added | — (grilling decision 5) | FR-027 | The scope in force on the reading branch is reported by the three queries. The PRD's FR-008 defines the rule; reporting its result is additive. |
| Minor | added | Open question 3 (enum or dropdown entries) | FR-020, Assumptions | Resolved to the PRD's stated default, "any required attribute", plus a refusal of list and JSON kinds, duplicates and the pool's own attribute. The last three are clarifications the PRD did not list; each is a refusal, not a capability. |
| Minor | changed | FR-009 "Validation runs against the schema of the branch the mutation runs on" | FR-009 (last sentence) | Added: an unchanged scope re-sent whole is accepted without re-validation. Needed because the scope is written once on the global branch (PRD's own decision) and a pool saved from a branch that knows an entry would otherwise be un-resavable from any branch that does not. The PRD's rule still applies to every scope that changes. |
| Major | changed | FR-011 (headline is the fullest division) | FR-011, FR-015, FR-017, User Story 3 scenarios 1 to 3 | Changed by the user on 2026-10-07: utilization on a scoped pool is read for one division at a time and refused without one; no figure reports the fullest division by default. The fullest division is the first row of the divisions list, which is ordered by utilization. Range rows report the division read. |
| Minor | changed | Assumptions: "P1 has landed", "the records lookup already resolves each record to its owning object", "relationships are processed before attributes" | Assumptions | Corrected against the code: P1 landed in part (the range kind, its mutations, the range migration and the shorthand mirror shipped; allocation over a range set and the shared effective-space calculation not yet), the records lookup does not resolve the holder, and the ordering holds on ordinary create only; the spec states the deferral that makes it hold on template create and update. The PRD's requirements are unchanged by the corrections. |
| Minor | changed | Edge case "a scoped pool over an attribute declared `unique: true`" | Edge Cases | Rewritten to describe today's behaviour (the global taken-values scan still masks the scope) and the post-P2 behaviour the PRD describes. No requirement changes; no test asserts the refusal. |
| Minor | added | — (user's delivery constraint, grilling decision 8) | Delivery order, User Story 1, FR-018, FR-019, SC-007, SC-010, SC-011 | The contract-first ordering, the frozen-contract rule and the fixed in-memory dataset the three queries return at contract time, with its removal test. These exist to meet the user's ask, not the PRD, and change no PRD behaviour. |
| Minor | changed | Journey P3 (consolidation) | User Story 7 | Marked deferred and gated on attach, which the code shows is not built; kept for traceability and listed as out of scope for this slice's definition of done. The PRD already states the dependency. |
| Minor | open | — (grilling decision 2) | Open points | Form A (several root fields) is published; form B (one root object) is to be re-judged at the final review of the surface. Recorded, not resolved. |
| None | — | FR-001 to FR-013, SC-001 to SC-006, user stories 1 to 16, journeys P1 and P2, key entities, out-of-scope list, implementation and testing decisions | same numbers; Traceability table | Present and unchanged in meaning. Implementation and testing decisions are carried into `plan.md` and `tasks.md` rather than reopened. |

## Action

Proceed. No remediation pass: nothing in the PRD is missing, dropped, softened or contradicted. The
additions resolve the PRD's own open questions, carry the user's delivery constraint and the
decisions of 2026-10-06, and the corrections replace assumptions the code does not support with
ones it does. Two items a PRD owner may want to confirm: the FR-017 per-range reporting choice,
recorded in the spec's Assumptions, and the form A versus form B choice recorded in Open points.

## Erratum (2026-10-07)

- Journey P3 / User Story 7: attach of a provided number is merged on `feature-number-pools-1.12`
  (a `<Kind>Update` sending `value` and `from_pool`), and User Story 7 is delivered by this epic
  (IFC-3357), one node per update, with no bulk attach mutation. The "deferred" finding above no
  longer applies; the spec's heading and the out-of-scope row are updated.
- Grilling decision 2 (form A versus form B): form A is kept, decided on 2026-10-07; the Open
  points section records the decision and no root field is renamed.
- FR-009 (validation branch): the scope is validated against the default branch's schema at pool
  save, whatever branch the mutation runs on (Notion PRD open question 2, its suggested default);
  the "unchanged scope accepted without re-validation" rule above is withdrawn, since every save
  validates against the same schema. A scope on a `unique: true` attribute and an entry not declared
  on the generic the pool serves are refused (Notion PRD FR-017 carve-out, FR-015). The allocation
  lock is keyed by pool and division (Notion PRD Mechanism "Lock", FR-031). Decided on 2026-10-07.
  The spec's Open points list the remaining departures from the Notion PRD for product confirmation.
- Assumptions row above ("P1 landed in part"): P1 has landed on `feature-number-pools-1.12` (the
  range kind, its mutations, the migration, `pools/number_ranges.py::EffectiveSpace`, allocation
  across the weighted ranges); the spec's Assumptions say so.
- Edge case "`unique: true`" row above: the edge case is a refusal at pool save and at schema load
  (FR-009, FR-010, FR-012), tested in IFC-3348, IFC-3351 and IFC-3352; "no test asserts the
  refusal" no longer applies.

## Erratum (2026-10-08)

- Division figures: a division's figures count the rows whose holder occupies the division on any
  live branch (FR-007 union), the same rows the `division` filter returns; `used_default_branch`
  counts those values held on the default branch. The contract example of Site C reads
  `used_default_branch` 1, `used_branches` 0. User decision of 2026-10-08.
- FR-012: `NumberPoolParameters.allocation_scope` ships with `update: NOT_SUPPORTED` (#10917), so a
  schema load cannot set, change or clear a declared scope on an existing attribute; the PRD's
  FR-012 and the Notion PRD's FR-018 amendment imply otherwise, and the spec lists the departure
  for confirmation.
- FR-032 (new): renaming a field a scope names rewrites the entry of every pool that names it,
  during the rename's schema migration; a rename on a branch rewrites the pools at merge. Proposed
  rule, listed for confirmation.
- FR-031: on a scoped pool the lock per pool and division replaces the mutation-level pool lock; an
  unscoped pool keeps the pool-level lock. No option is left open.
