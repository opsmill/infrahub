# Coalesced Recompute on Merge and Rebase

> Part of: `dev/knowledge/backend/` | Related: [computed-attributes.md](computed-attributes.md), [display-labels-and-hfid.md](display-labels-and-hfid.md), [selective-merge-regeneration.md](selective-merge-regeneration.md), [events.md](events.md)

A live edit recomputes derived values one node at a time (see [computed-attributes.md](computed-attributes.md)). A merge or rebase can change many nodes at once, so it uses a different path: one coalesced recompute for the whole change set, written in bulk, then chained to any value that reads what was written.

This covers three derived-value families: Jinja2 computed attributes, display labels, and human-friendly ids. Python-transform computed attributes and profile refresh are not part of this coalesced pass; they are dispatched by their own automations, though the Python transforms process their fan-out as batches persisted through the same bulk writer (see [computed-attributes.md](computed-attributes.md)). Generator and artifact regeneration on merge takes its own selective path, described in [selective-merge-regeneration.md](selective-merge-regeneration.md).

## Why a separate path

The per-node path emits one node event per changed node, and Prefect matches each event against every recompute automation. A large merge therefore starts one flow per changed node per family, and nothing dedups across nodes. The coalesced path replaces that fan-out with a single deduplicated pass: it works out once which derived values the change set affects, then submits one flow per affected value. The stored values are the same. The work scales with the number of affected derived values, not with the changed-node count.

## The flow

```text
merge / rebase
  -> stamp node events with origin = merge | rebase   (suppresses the 3 families' per-node triggers)
  -> CoalescedRecomputeBuilder.build(changes, branch)  (diff changelog -> deduplicated target set)
  -> CoalescedRecomputeSubmitter.submit(...)           (one process flow per target and source kind)
       -> computed_attribute_process_jinja2 / display-label-process-jinja2 / hfid-process
            -> render values, keep only the ones that changed
            -> BulkRecomputeDispatcher.dispatch(writes, coalesced=True, recompute_depth)
                 -> BulkRecomputeWriter.write(...)         (bulk write, origin = recompute)
                 -> RecomputeChainSubmitter.submit(...)    (dispatch the next level for readers of the writes)
```

The builder, submitter, and coordinator live in `core/merge/recompute_coalescing.py`. The build step is pure, so it is unit and component testable without a database or a worker. A merge recomputes on the destination branch; a rebase recomputes on the user branch.

## Node mutation origin

Every node mutation event carries an `origin` label (`infrahub.node.origin`), one of:

| Origin | Set by | Meaning |
|--------|--------|---------|
| `live` | default | A direct edit through the API. |
| `merge` | the merge post-process | A replay of a merged change. |
| `rebase` | the rebase flow | A replay of a rebased change. |
| `recompute` | the bulk writer on a coalesced pass | A derived-value recompute write. |

The three families' cross-node triggers match only `live`, so `merge`, `rebase`, and `recompute` events do not start their per-node flows. This is what lets the coalesced pass be the single dispatcher for those families without double-processing. Other consumers (user action rules, webhooks, Python-transform computed attributes, profiles) keep receiving every event whatever the origin.

**Location:** `events/constants.py` (`NodeMutationOrigin`, `NODE_ORIGIN_LABEL`); the `live`-only match is set in each family's trigger builder (`computed_attribute/models.py`, `display_labels/models.py`, `hfid/models.py`).

## The bulk writer

**Location:** `core/recompute/bulk_write.py` (`BulkRecomputeWriter`), driven through `core/recompute/dispatch.py` (`BulkRecomputeDispatcher`)

The process flows render the new values, keep only the ones that differ from the stored value, and hand them to a `BulkRecomputeDispatcher` (wired by `build_bulk_recompute_dispatcher`). This is the single write path for all three families, on both the live and the coalesced side. The `coalesced` flag is the difference: a live single-node recompute passes `coalesced=False` (stamp `live`, let the emitted events carry any further readers), a merge, rebase, or chained level passes `coalesced=True` (stamp `recompute`, drive the next level here).

The writer:

- Groups the writes by node, so a node reached by several families is saved once.
- Loads the whole node, not just the written fields. A save recomputes same-node derived values that read a written value (for example a display label that reads a computed attribute), and it can only do that when they are loaded.
- Applies the writes in bounded transaction chunks to keep the lock footprint contained.
- Skips a no-op save. A recompute can render the value already stored, so that node emits no event and does not chain.
- Emits one `NodeUpdatedEvent` per node, carrying every field the save changed (including same-node cascades), so cross-node readers of those fields still recompute.

Writes commit per chunk and emit before the next chunk runs, so the write is not atomic across chunks. A mid-run failure can leave earlier chunks written. Recovery relies on the flow re-running and re-detecting no-ops.

## Chaining and the depth bound

A recompute write can feed a value that reads it on another node. On a coalesced pass, after the bulk write, `RecomputeChainSubmitter` treats the writes as a new change set and dispatches the next coalesced level for their readers. Each level carries an incremented `recompute_depth`.

An empty write set dispatches nothing, which is the normal stop: an acyclic dependency graph settles on its own because each level only writes the values that actually changed. The depth bound only guards a cyclic or self-referential schema, which never settles. It is derived from the schema (`max_recompute_chain_depth` in `recompute_coalescing.py`): a chain cannot recompute more derived values than the schema defines, so the bound is the derived-value target count, with a floor. That never truncates a real acyclic chain, however deep, and still stops a cyclic one. Reaching it logs a warning that the graph is likely cyclic and names the nodes left unrecomputed.

## Live path vs coalesced path

| Trigger | Path | Origin | Chains via |
|---------|------|--------|------------|
| Direct edit, same node | inline during `Node._update()` | n/a | inline, in dependency order |
| Direct edit, reader on another node | per-node async process flow, `coalesced=False` | `live` | the emitted `live` events and their per-node triggers |
| Merge or rebase | coalesced pass, `coalesced=True` | `recompute` | `RecomputeChainSubmitter` |
| A recompute write feeding a reader | chained coalesced pass, `coalesced=True` | `recompute` | `RecomputeChainSubmitter`, depth-bounded |

## Key Files

| File | What |
|------|------|
| `core/merge/recompute_coalescing.py` | `CoalescedRecomputeBuilder`, `CoalescedRecomputeSubmitter`, `MergeRecomputeCoordinator`, `RecomputeChainSubmitter`, `max_recompute_chain_depth` |
| `core/recompute/bulk_write.py` | `BulkRecomputeWriter`, `AttributeValueWrite`, `WrittenNode` |
| `core/recompute/dispatch.py` | `BulkRecomputeDispatcher`, `build_bulk_recompute_dispatcher` (bulk write, then chain on a coalesced pass) |
| `core/merge/post_merge.py` | Merge: stamp `merge` origin, build and submit on the destination branch |
| `core/branch/tasks.py` | Rebase: stamp `rebase` origin, build and submit on the user branch |
| `events/constants.py` | `NodeMutationOrigin`, `NODE_ORIGIN_LABEL` |
| `computed_attribute/tasks.py`, `display_labels/tasks.py`, `hfid/tasks.py` | The three process flows that render values and call `BulkRecomputeDispatcher.dispatch` |

## See Also

- [Computed Attributes](computed-attributes.md) - the live evaluation paths for Jinja2 computed attributes
- [Display Labels & HFID](display-labels-and-hfid.md) - the same for display labels and human-friendly ids
- [Selective Post-Merge Regeneration](selective-merge-regeneration.md) - the sibling merge-followup path for generators and artifacts
- [Events System](events.md) - node mutation events and the `origin` metadata
- [Merge Failure Recovery](merge-failure-recovery.md) - reversing a merge that died before the post-`MERGED` recompute
