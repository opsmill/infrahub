# Phase 0 Research: Coalesce merge and rebase recompute fan-out

**Date**: 2026-06-26 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Grounded in the profile (first task on IFC-2761), the code analysis recorded on the ticket, and the two setup spikes (R3, R5). File:line anchors describe **current develop**; the branch is now rebased onto current develop (R9), so the anchors are real. R3 and R5 are resolved by the spikes; remaining items are confirmed during implementation. Reuse over rebuild (Constitution VII).

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

## R3. No double processing (FR-008) — RESOLVED (T002 spike)

**Finding (corrects the earlier wording)**: the exclusion that makes same-node changes free is not a merge-origin filter. Self-targeting recompute triggers (`targets_self`) are built with a placeholder field (`TRIGGER_PLACEHOLDER_FIELD`, `trigger/constants.py`) that no real node event ever carries, so they never match a `NodeMutatedEvent` from any source (live, merge, or rebase); the same-node value is written inline during the save and carried over by the merge instead. The asynchronous cost is the cross-node triggers (`targets_self=False`, real fields) matching the per-node events.

**Emission shape**: a merge emits one `NodeMutatedEvent` per changed node on the destination branch, parented to a `BranchMergedEvent` (`core/merge/post_merge.py`); a rebase emits on the user branch, parented to a `BranchRebasedEvent` (`core/branch/tasks.py`, gated by `send_events`). Neither carries a merge/rebase-origin marker today; the only origin signal is the event lineage (`meta.parent` / `meta.ancestors`), which is not exposed as a Prefect match label.

**Other consumers of the per-node events (must keep working)**: user-defined action / node-trigger rules (`actions/models.py`) consume the same `NodeCreated/Updated/Deleted` events with no origin discrimination and do fire on merge today; webhook-config and action-rule-setup triggers match only config-node kinds. Generators are re-run on merge independently of node events (`post_process_branch_merge`, source=MERGE). So dropping per-node emission on the merge/rebase path (option a) would silently break user action rules and is rejected.

**Decision (option b)**: keep emitting the per-node events; stop only the coalesced families' cross-node triggers from matching merge/rebase-origin events, and make the coalesced pass their single dispatcher. Mechanism:
- stamp a merge/rebase-origin discriminator on the node events at the two build sites (a new `EventMeta` field surfaced as a match label, e.g. `infrahub.node.origin`, preferred over deriving origin from `ancestors`/event-name strings);
- add a negative match (origin is not merge/rebase) to the trigger builders of exactly the families the coalesced pass covers: Jinja2 computed attributes (`computed_attribute/models.py`), display labels (`display_labels/models.py`), human-friendly ids (`hfid/models.py`);
- leave the families not coalesced in this increment on the per-node path unchanged: Python-transform computed attributes, the profile-refresh family (`profiles/models.py`), action rules, and webhooks.

**Residual risk (the core of T012/T014)**: the coalesced pass MUST itself recompute the cross-node (`targets_self=False`) readers that the suppressed events used to drive; the existing self-targeting setup path only covers `targets_self=True`. Missing this is the main correctness gap. The profile-refresh family is a fourth recompute family that is easy to overlook; it is intentionally left out of scope and out of the suppression set so it keeps its current behavior.

## R4. Recompute execution — reuse process flows + batch/chunk

**Decision**: feed the coordinator's deduplicated target set into batched invocations of the existing per-family flows (`process_jinja2` / `process_display_label` / `process_hfid` and their `*_update_value`), reusing `client.create_batch()` and the existing chunking helpers. The coordinator submits a single batched recompute over the union of affected node ids per family.

**Related fix (R8)**: on current develop the full-branch Jinja2 recompute loop submits one workflow per node with no chunking, unlike the Python/transform paths; chunk it while in the same area.

## R5. Redundancy on the merge path (FR-015) — RESOLVED (T003 spike): recompute-all default

**Finding**: derived values (Jinja2 computed attributes, display label, human-friendly id) are stored graph attributes, not computed on read (`core/node/node_property_attribute.py`; the read path does not recompute when a stored value exists). Same-node values recompute inline inside the save transaction on a branch (`core/node/__init__.py`), and the graph merge copies attribute property edges, including these, into the destination (`core/diff/merger/merger.py`). So a value computed on the source branch arrives on the destination already correct for its own node; the post-merge asynchronous cost is purely the cross-node reader fan-out.

**Finding**: the post-merge dispatch fans out for the changed-node set only (`post_merge.py` over the merge diff), not all nodes. The existing scoping (the #9415 work and the per-trigger branch filters; invariant asserted by `test_merge_does_not_trigger_schema_scoped_recompute`: a merge never broadens recompute onto the default branch) concerns the schema-scoped path and branch isolation; it does NOT dedup source-vs-destination data-reader redundancy, and no such dedup exists today.

**Finding**: the genuine must-recompute set is the readers that exist only on the destination branch, or whose relationship to the changed node exists only on the destination: the source branch's live fan-out never touched them. These are discoverable only by a destination-branch graph query, not from the diff payload. Rebase is symmetric: source = default branch, recompute destination = user branch; the must-recompute set is the readers only on the user branch.

**Decision**: recompute all affected readers on the correct branch (destination for merge, user for rebase). This is the safe default and never under-recomputes (FR-002/FR-015). The source-branch-redundancy skip is deferred (T019) and is likely not worth it: a reader is provably redundant only under a strict conjunction (reader and its relationship present on the source branch, the source async fan-out actually completed before merge, the merged value not base-resolved by conflict handling, no schema/template change to its derivation), and proving it needs a source-vs-destination branch query plus a conflict-resolution check whose cost rivals the recompute avoided, while adding correctness risk (the source fan-out is best-effort and not awaited by the merge). Revisit only if the harness shows reader overlap is a measured hotspot after coalescing lands.

## R6. Correctness oracle and verification

**Decision**: prove correctness on the full stack by comparing post-merge derived values against a from-scratch recompute, for cross-node, transitive, creation, and deletion cases, on the correct branch per operation. Measure performance with the profiling harness from the first task (FR-011). integration_docker is the required level for triggered actions (Constitution IV).

## R7. Rebase parity and branch difference

**Decision**: apply the coordinator in the rebase flow too, recomputing on the **user branch** (merge recomputes on the **destination branch**). The diff changelog shape is the same; the coordinator is shared, the branch argument differs (FR-014).

## R8. Targeting precision with a bounded fallback (from clarification)

**Decision**: precise where the derivation supports it; a bounded, **logged** safe over-approximation only where precise derivation is unavailable (e.g. a deletion or transitive case the metadata does not resolve), never silent under-recompute (FR-012). The unchunked Jinja2 loop fix (R4) belongs here as an opportunistic improvement.

## R9. Branch base — DONE

**Decision**: rebased `coalesce-merge-recompute-ifc-2761` onto current develop (`f1e69c9dd`); the integration points above (`post_merge.py`, the per-family triggers, the unchunked Jinja2 loop) are now the real ones. The in-flight stable→develop merge (`gm-merge-stable-into-develop`) is identical to develop across the whole merge/recompute area: its tip restores `orchestrator.py` and `post_merge.py` to develop's versions and explicitly defers reconciling #9602 (post-merge refresh of nodes absent from the source) with #9415 (scoped recompute) to this ticket, so rebasing onto develop targets the canonical code and that reconciliation is in scope here (see the IFC-2758 coordination item). The harness builds and runs on develop after one adaptation: develop's merge/rebase path reads a Redis-backed write blocker, so the counting layer injects the in-memory cache adapter.

## Out of scope

- Python-transform computed attributes (follow-up, same approach).
- Background task scheduling / throughput tuning (separate effort).
- Schema-changing merges (migrations) — a different recompute path; see IFC-2758.
- A configurable per-instance recompute policy.

## Open items carried into tasks

- **R3** (RESOLVED): keep per-node emission; stamp a merge/rebase-origin label and add a negative match to the three coalesced families' triggers only (computed Jinja2, display, HFID), leaving Python-transform, profiles, action rules, and webhooks on the per-node path. Carry the residual into T012/T014: the coalesced pass must itself drive the cross-node (`targets_self=False`) readers the suppressed events used to handle.
- **R5** (RESOLVED): recompute all affected readers on the correct branch; the source-branch-redundancy skip (T019) is deferred and likely not worth it (cost of proving a reader safe rivals the recompute, with best-effort source fan-out as a correctness risk).
- **R2/Constitution V**: confirm the coordinator resolves per signature and queries readers once over the union (no N+1).
- **IFC-2758 coordination**: definition-only schema changes do not refresh nodes absent from the source branch (merge emits no schema-updated event). The stable→develop merge defers the #9602/#9415 reconciliation to this ticket; treat it as in scope and avoid double processing.
- **R9** (DONE): rebased onto current develop; anchors are real.
