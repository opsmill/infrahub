# Phase 0 Research: Coalesce merge and rebase recompute fan-out

**Date**: 2026-06-26 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Grounded in the profile (first task on IFC-2761) and the code analysis recorded on the ticket. File:line anchors describe **current develop**; this spec branch is based on the older profile branch and must be rebased onto current develop before implementation (see R9). Items marked OPEN are confirmed during implementation. Reuse over rebuild (Constitution VII).

## R1. How recompute is wired today, and where to intercept

**Finding**: merge and rebase do not recompute anything themselves. After the graph merge they walk the diff changelog and send one node event per changed node; Prefect matches each event against every recompute automation, and each match starts a flow that runs its own reader query plus one update per reader. No batching, no dedup.

- Merge emits in the post-merge dispatcher: `backend/infrahub/core/merge/post_merge.py`.
- Rebase emits inline in the rebase flow: `backend/infrahub/core/branch/tasks.py`.
- Both build the diff changelog (set of changed nodes with kind + changed fields) and loop. **Branch difference**: merge sends on the destination branch; rebase sends on the user branch.

**Decision**: intercept at the same point — where the full set of changed (kind, field) pairs is already known — and submit one coalesced recompute instead of the per-node events. The interception is per operation (merge in `post_merge.py`, rebase in `tasks.py`) but the coordinator is shared.

## R2. Deriving the affected targets — reuse computed, build display/HFID here

**Finding**: each recompute family registers Prefect automations per branch, per derived value, per source kind; an async peer-change trigger exists only when the derived value reads across a relationship (so a self-only HFID gets none; a peer-reading display label does). The families therefore do not share one rule.

**Decision**: build the coalesced selection from the changed (kind, field) pairs and created/deleted nodes, deduplicated, reusing derivation:
- computed attributes: reuse the existing deriver / scoping (`computed_attribute/scoping.py`, PR #9467).
- display labels and human-friendly ids: **no shared deriver exists** (IFC-2759 closed as not applicable; those families are scoped on the schema-update path by trigger-modification detection, so none was built). Build the deriver here, following the computed-attribute pattern, reading the dependency metadata already recorded on the display-label and HFID definitions (attributes, relationships, relationship fields, exposed via the schema-branch facades `schema_branch_display.py` / `schema_branch_hfid.py`).

**Constraint (Constitution V)**: resolve targets per distinct `(kind, changed-fields)` signature (the changed-node set collapses to few signatures), then dedup target types, then resolve the affected node ids with **one query over the union** of readers — not one flow + one reader query per changed node, which is the fan-out being removed.

## R3. No double processing (FR-008)

**Finding**: self-targeting automations are already disabled on the replayed merge events on purpose (same-node values were computed on the source branch and carried over), which is why same-node changes are free. The cost is the **cross-node** automations firing per event.

**Decision**: the coalesced pass becomes the single dispatch for cross-node recompute on the merge/rebase path; the per-node events must not also trigger the cross-node automations for the same change. Mechanism options (resolve first, OPEN):
- stop emitting the per-node recompute-triggering events on the merge/rebase path (simplest) — only safe if no downstream consumer needs them;
- or keep them for other consumers and exclude merge-origin events from the cross-node automations.
First map the consumers of merge-emitted node events, then pick the simplest mechanism. Coordinate with the merge data-event path so the coalesced pass and any retained events do not both recompute.

## R4. Recompute execution — reuse process flows + batch/chunk

**Decision**: feed the coordinator's deduplicated target set into batched invocations of the existing per-family flows (`process_jinja2` / `process_display_label` / `process_hfid` and their `*_update_value`), reusing `client.create_batch()` and the existing chunking helpers. The coordinator submits a single batched recompute over the union of affected node ids per family.

**Related fix (R8)**: on current develop the full-branch Jinja2 recompute loop submits one workflow per node with no chunking, unlike the Python/transform paths; chunk it while in the same area.

## R5. Redundancy on the merge path (OPEN — needs a trace before designing skip logic)

**Finding**: some post-merge reader recompute may be redundant with recompute that already ran on the source branch and was merged in. Readers that exist **only on the destination branch** were never touched and must recompute. Readers already recomputed on the source branch and merged in may not need it.

**Decision**: default to recompute (never under-recompute, FR-002/FR-015). Treat skipping source-branch-already-recomputed readers as an optimization gated on a trace that proves which readers are safe to skip. Do the trace before designing the skip; do not assume.

## R6. Correctness oracle and verification

**Decision**: prove correctness on the full stack by comparing post-merge derived values against a from-scratch recompute, for cross-node, transitive, creation, and deletion cases, on the correct branch per operation. Measure performance with the profiling harness from the first task (FR-011). integration_docker is the required level for triggered actions (Constitution IV).

## R7. Rebase parity and branch difference

**Decision**: apply the coordinator in the rebase flow too, recomputing on the **user branch** (merge recomputes on the **destination branch**). The diff changelog shape is the same; the coordinator is shared, the branch argument differs (FR-014).

## R8. Targeting precision with a bounded fallback (from clarification)

**Decision**: precise where the derivation supports it; a bounded, **logged** safe over-approximation only where precise derivation is unavailable (e.g. a deletion or transitive case the metadata does not resolve), never silent under-recompute (FR-012). The unchunked Jinja2 loop fix (R4) belongs here as an opportunistic improvement.

## R9. Branch base

**Decision**: rebase `coalesce-merge-recompute-ifc-2761` onto current develop before implementation. The integration points above (`post_merge.py`, the unchunked Jinja2 loop) exist on current develop, not on this older spec branch. Coordinate with the in-flight stable→develop merge.

## Out of scope

- Python-transform computed attributes (follow-up, same approach).
- Background task scheduling / throughput tuning (separate effort).
- Schema-changing merges (migrations) — a different recompute path; see IFC-2758.
- A configurable per-instance recompute policy.

## Open items carried into tasks

- **R3** (blocking): map consumers of merge-emitted node events; choose drop-emission vs exclude-from-automations; gates FR-008.
- **R5** (blocking the skip optimization): trace which readers were already recomputed on the source branch; until then, recompute all affected readers.
- **R2/Constitution V**: confirm the coordinator resolves per signature and queries readers once over the union (no N+1).
- **IFC-2758 coordination**: definition-only schema changes do not refresh nodes absent from the source branch (merge emits no schema-updated event); avoid double processing.
- **R9**: rebase onto current develop so anchors are real.
