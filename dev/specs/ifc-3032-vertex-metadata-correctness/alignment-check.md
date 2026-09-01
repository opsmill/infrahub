# Spec / Ask Alignment Check: IFC-3032

**Date**: 2026-08-31
**Spec**: [spec.md](spec.md)

## 1. Source

| Source | Status | Used |
|---|---|---|
| `IFC-3032-brief.md` (repo root) | Available inline; substantive PRD (~18 KB) | Yes |
| <https://opsmill.atlassian.net/browse/IFC-3032> | **Resolved** via the authenticated Atlassian connector. The brief states this URL was *not* read ("Jira behind auth; brief built from the seed description plus code investigation") | Yes — **authoritative** |

The Jira ticket is the true source of truth and it was **not** available when the brief was written.
The brief is a faithful and much deeper elaboration of the ticket's *first* concern, but it silently
drops two others. Comparing the spec only against the brief would have reported ✅ ALIGNED and missed
both.

**Ticket description, verbatim scope items**:

1. Metadata not correctly set on branch-agnostic attributes and relationships of branch-aware objects.
2. Check these paths for correctness: **object create**, **object/field update**, **object delete**,
   **schema updates** (attribute add, attribute remove, relationship remove, "… more?").
3. "We do not believe we need to make any changes to merge or rebase logic b/c branch-agnostic fields
   are excluded from a merge/rebase by definition."
4. "We also need to account for setting the `previous_updated_at/by` properties on branch-agnostic
   fields. These are used during a rollback of a failed merge… **Rollback needs to correctly support
   these branch-agnostic field metadata properties as well.**"

## 2. Verdict

### Pass 1 — 🛑 SIGNIFICANT DRIFT

Two of the ticket's four scope items were absent from the spec, both verified as real gaps in code.

### Pass 2 (after remediation) — ✅ ALIGNED

See § 5.

## 3. Findings (pass 1)

| Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|
| 🛑 High | **missing** | Ticket item 4 — "Rollback needs to correctly support these branch-agnostic field metadata properties as well" | No FR; `GraphRollbacker` appeared only in the critique, and in the *opposite* direction | `core/query/rollback.py::RollbackReopenEdgesQuery` and `::RollbackDeleteEdgesQuery` both match `(src)-[edge {branch: $target_branch}]->(dst)` — a **single** branch. A merge into the default branch that runs a schema migration adding or removing an agnostic field on an aware kind writes those edges to `-global-`, so a failed-merge rollback never sees them: the edges are not reversed and the vertex metadata they bumped is never restored from `previous_updated_at/by`. This is precisely the scenario the ticket calls out, and the spec had no requirement for it |
| 🛑 High | **missing** | Ticket item 2 — "object delete" listed as a path to check | Delete appeared only as a test axis in SC-001 and indirectly via FR-004 | `core/query/node.py::NodeDeleteQuery` gates its Node-vertex bump on `if self.branch.is_global or self.branch.is_default` — the same object-level proxy FR-001 fixes for the update path, unfixed for delete. An **aware** node deleted on a user branch skips the bump, while its agnostic attributes' deletion edges land on `-global-` at level 1 and are visible on the default branch. A third live instance of F1 that no requirement covered |
| ✅ | aligned | Ticket item 1 | F1, F1b, mismatches #1–#4 | Fully covered, and substantially deepened |
| ✅ | aligned | Ticket item 2 — create / update / schema updates | FR-003 / FR-001 / FR-007 | Covered. The spec's enumeration of all seven migration queries answers the ticket's "… more?" |
| ✅ | aligned | Ticket item 3 — no merge/rebase change needed | Assumptions: "`DiffMergeMetadataQuery` … needs no change" | Agrees with the ticket's own reasoning |
| ⚠️ Note | changed | Ticket item 4 | Critique finding E3 | The critique concluded FR-007 should **skip** the `previous_*` snapshot on user branches, unaware the ticket scoped rollback support in. The two are reconcilable rather than contradictory — see § 4 — but the conclusion was reached without the governing requirement in hand |

## 4. Reconciling the critique's E3 with the ticket

These address different branches and both hold:

- **Schema migration on a user branch** (critique E3): not part of a merge. `GraphRollbacker.rollback`
  *raises* if asked to restore metadata for a non-default target branch, so a snapshot written there
  can never be consumed. Skipping it stays correct.
- **Schema migration during a merge into the default branch** (the ticket's named case):
  `$set_metadata` is already true, the snapshot **is** written, and the rollback must restore it — but
  cannot today, because the rows live on `-global-` while the rollback scans only the target branch.

The first is about not writing an unusable snapshot; the second is about consuming one that is
already written. Remediation adds the second without disturbing the first.

## 5. Action

**Remediation passes used: 1 of 2.**

Pass 1 added two requirements and threaded them through every downstream artifact:

- **FR-008** — the delete path (`Node.delete` / `NodeDeleteQuery`) gates on the deleted fields' edge
  level, not the node's branch support. Folded into User Story 1/2's gate work, since it is the same
  defect on a third path.
- **FR-009** — `GraphRollbacker` reverses level-1 `-global-` writes made during a merge into the
  default branch, and restores the `previous_updated_at/by` snapshots on the vertices they bumped.
  Carries its own user story (US5) and its own success criterion (SC-004).

Downstream updates: `plan.md` (D9, D10, Constitution re-check, Risks), `research.md` (R10),
`contracts/vertex-metadata-invariant.md` (rollback consumer), `quickstart.md` (scenario 5),
`tasks.md` (Phase 3 delete tasks, new Phase 8 for rollback, renumbered).

## 6. Pass 2 re-check

Re-ran the critique against the newly added scope (see the addendum in
`critiques/critique-20260831-175232.md`), then re-compared spec.md to the ticket.

**Ticket item coverage**:

| Ticket scope item | Spec coverage | Status |
|---|---|---|
| Metadata on agnostic fields of aware objects | F1, F1b, mismatches #1–#4 | ✅ |
| Path: object create | FR-003 | ✅ |
| Path: object/field update | FR-001, FR-002 | ✅ |
| Path: object delete | **FR-008** (added this pass) | ✅ |
| Path: schema updates — attribute add | FR-007 | ✅ |
| Path: schema updates — attribute remove | F6 table: `attribute_remove` is self-consistent, with the reason | ✅ |
| Path: schema updates — relationship remove | F6 table: `node_relationship_remove` is self-consistent, with the reason | ✅ |
| Path: schema updates — "… more?" | All seven migration queries enumerated in F6 | ✅ |
| No merge/rebase logic change needed | Assumptions agree, with the F6 caveat that merge cannot self-heal global rows | ✅ |
| `previous_updated_at/by` on agnostic fields | FR-007 (do not write an unusable snapshot) + FR-009 (consume the ones a merge writes) | ✅ |
| Rollback must support agnostic field metadata | **FR-009** (added this pass), SC-004 | ✅ |

**New finding raised during the re-critique** (not drift — a hazard in the remediation itself):
FR-009's widening is unsafe under `SINCE_TIMESTAMP`, because the merge write-block leaves branches
other than the source and the default free to write to `-global-` during the merge window. Resolved by
pinning the `-global-` half to exact-timestamp semantics, with an implementation-time verification
gate (tasks T064) and a regression pin (T063).

**No scope added beyond the ticket.** FR-008 and FR-009 map one-to-one onto ticket items; nothing else
was introduced.

**Pass 2 verdict**: ✅ **ALIGNED**.
