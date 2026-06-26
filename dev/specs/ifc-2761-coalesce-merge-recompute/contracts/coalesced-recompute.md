# Contract: Coalesced merge/rebase recompute (internal)

**Date**: 2026-06-26 · **Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md)

No external (REST/GraphQL) surface changes. The contracts here are the internal coordinator entry point and the invariants the merge and rebase paths must hold, so behavior is preserved and existing components are reused. Per `dev/rules/code-doc-style.md`, shipped source carries no spec IDs. Anchors describe current develop (see research R9).

## 1. The coordinator

**Location**: `backend/infrahub/core/merge/recompute_coalescing.py` (new; final placement confirmed in implementation)

```python
def build_coalesced_recompute(*, changes, schema_branch, branch) -> CoalescedRecompute: ...
    # Pure: turn the diff changelog (set of MergeChange) into the deduplicated set of
    # affected derived-value targets across computed attributes, display labels, and
    # human-friendly ids, tagged with the branch the recompute runs on. Groups by
    # ChangeSignature; reuses the computed-attribute deriver and the new display/HFID
    # deriver built to the same pattern. No DB writes, no Prefect.

async def submit_coalesced_recompute(*, request, context, ...) -> None: ...
    # Submit one batched/chunked recompute over request.targets, resolving reader node
    # ids with a single query over the union per family, reusing the existing per-family
    # process/update flows. No per-node fan-out, no per-target reader re-query.
```

**Guarantees**:
- `build_coalesced_recompute` is pure and deterministic — the unit/component-testable core.
- Derivation reuses the computed-attribute deriver and the new display/HFID deriver (built to the same pattern from the recorded definition metadata), so it cannot diverge from the live per-node path (FR-007).
- Target resolution is per distinct `ChangeSignature`, deduplicated, with readers resolved by one union query (Constitution V) — it does not re-create the fan-out.
- Coverage: cross-relationship readers on update; all families on creation; readers of deleted nodes; readers existing only on the destination branch (FR-005, FR-013, FR-015). Where a case cannot be resolved precisely, a bounded, logged over-approximation is emitted (`precise=False`, FR-012) — never silent under-recompute.
- The result carries the branch the recompute runs on (FR-014).

## 2. The merge and rebase integration

**Merge**: `backend/infrahub/core/merge/post_merge.py` — where the post-merge dispatcher walks the diff changelog. Build and submit the `CoalescedRecompute` on the **destination branch** instead of the per-node cross-node fan-out.

**Rebase**: `backend/infrahub/core/branch/tasks.py` — inline in the rebase flow. Same coordinator, on the **user branch**.

**No-double-processing invariant (FR-008)**: a single change is recomputed by exactly one path. Self-targeting automations are already disabled for replayed merge events; the coalesced pass must also stop the **cross-node** automations from firing for the same change (drop the per-node recompute-triggering emission, or exclude merge-origin events). Resolved in research R3.

**Behavior-preserving invariant (FR-010)**: the derived values stored after the merge/rebase are identical to today; only the work changes. **Branch invariant (FR-014)**: merge recomputes on the destination branch, rebase on the user branch.

## 3. Reused vs built components

| Need | Status | Source |
|------|--------|--------|
| Change set | reuse | diff changelog the merge/rebase already collects (`post_merge.py` / `core/branch/tasks.py`) |
| Computed-attribute deriver | reuse | `computed_attribute/scoping.py` (PR #9467) |
| Display-label / HFID deriver | **build here** | new, to the computed pattern, from the metadata on the definitions (`schema_branch_display.py`, `schema_branch_hfid.py`) |
| Per-family execution + batch/chunk | reuse | `{computed_attribute,display_labels,hfid}/tasks.py` + `client.create_batch()` + chunk helpers |

## 4. Related fix (opportunistic)

The full-branch Jinja2 recompute loop submits one workflow per node without chunking on current develop, unlike the Python/transform paths; chunk it while in the same area (research R4/R8).

## Out of scope

- Python-transform computed attributes (follow-up).
- Background task scheduling / throughput tuning.
- Schema-changing merges (migrations); see IFC-2758 for the complementary correctness gap.
- Any change to the final derived values (behavior-preserving only).
