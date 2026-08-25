# Coalesced Recompute on Merge and Rebase

> Part of: `dev/knowledge/backend/` | Related: [computed-attributes.md](computed-attributes.md), [display-labels-and-hfid.md](display-labels-and-hfid.md), [selective-merge-regeneration.md](selective-merge-regeneration.md), [events.md](events.md)

A live edit recomputes derived values one node at a time (see [computed-attributes.md](computed-attributes.md)). A merge or rebase can change many nodes at once, so it uses a different path: one coalesced recompute for the whole change set, written in bulk, then chained to any value that reads what was written.

This covers four derived-value families: Jinja2 computed attributes, display labels, human-friendly ids, and Python-transform computed attributes. The Python family is described in [The Python transform family](#the-python-transform-family) below and is governed by `INFRAHUB_COALESCE_PYTHON_RECOMPUTE_AFTER_MERGE`, on by default. Profile refresh is not part of the pass; it is dispatched by its own automations. Generator and artifact regeneration on merge takes its own selective path, described in [selective-merge-regeneration.md](selective-merge-regeneration.md).

## Why a separate path

The per-node path emits one node event per changed node, and Prefect matches each event against every recompute automation. A large merge therefore starts one flow per changed node per family, and nothing dedups across nodes. The coalesced path replaces that fan-out with a single deduplicated pass: it works out once which derived values the change set affects, then submits one flow per affected value. The stored values are the same. The work scales with the number of affected derived values, not with the changed-node count.

## The flow

```text
merge / rebase
  -> stamp node events with origin = merge | rebase   (suppresses the 4 families' per-node triggers)
  -> CoalescedRecomputeBuilder.build(changes, branch)  (diff changelog -> deduplicated target set)
  -> CoalescedRecomputeSubmitter.submit(...)           (one process flow per target and source kind)
       -> computed_attribute_process_jinja2 / display-label-process-jinja2 / hfid-process
            -> render values, keep only the ones that changed
            -> BulkRecomputeDispatcher.dispatch(writes, recompute_depth)   (built for a coalesced pass)
                 -> BulkRecomputeWriter.write(...)         (bulk write, origin = recompute)
                 -> RecomputeChainSubmitter.submit(...)    (dispatch the next level for readers of the writes)
```

The builder, submitter, and coordinator live in `core/merge/recompute_coalescing.py`. The build step is pure, so it is unit and component testable without a database or a worker. A merge recomputes on the destination branch; a rebase recomputes on the user branch.

## The Python transform family

**Location:** `core/merge/python_target_resolution.py` (the narrowing), `core/merge/python_target_sources.py` (the database and client sources)

A Python transform declares no dependency graph. What it reads is only known from its GraphQL query, and which nodes read a given node is only known from the query groups those nodes subscribed to when they last computed. Both are database facts, so this family is derived behind an interface (`PythonTargetResolver`) instead of from the schema branch the builder holds.

`INFRAHUB_COALESCE_PYTHON_RECOMPUTE_AFTER_MERGE` governs the family, on by default, and it governs **both halves at once**: the real resolver against an inert one, and whether the two Python per-node automations carry the `live` origin filter. Setting it to `false` restores the per-node dispatch on merge and rebase in one step. Keep the two halves on the same switch: with the filter applied and the resolver inert, nothing would recompute a replayed change.

The derivation applies the same per-action rules as the other families: a created node is its own target, an update selects the readers of the changed fields and, when the updated node is of the target kind, that node itself, a deletion selects the readers too. On top of that:

- **Read sets come from the analyzed transform queries.** A field the query does not read selects nothing. Imprecision is held per kind, so a query reading a derived field of one kind still rejects an unread field of another.
- **Readers come from the query-group subscriber index**, one union query per set of changed ids, never one per changed node.
- **An updated node of the target kind is also a target of its own**, next to the reader lookup. The reverse index only reaches a node that computed successfully at least once, since that is when it subscribed; a node whose first compute failed would otherwise keep a stale value after its own read field is merged. This is what makes the pass cover everything the owner automation covered.
- **A deleted node id is resolved in a lookup of its own.** Sharing one with live ids empties the whole result, which would drop the readers of the live changes. A deleted node holds no open membership edge any more, so its own lookup answers nothing; a reader that pointed at it is carried by its own relationship update, which the change set holds.
- **Every signal that cannot be narrowed widens to the whole target kind**, and is logged. An undeterminable read set and a failed reader lookup both widen. A widened target carries no node ids and goes to `trigger_update_python_computed_attributes` instead of `computed_attribute_process_transform`; the `whole_kind` flag is what carries that case to the submission planner, since chunking an empty id set would produce no submission at all.
- **A schema-changing merge already refreshes what its own scope selects**, one whole kind at a time, through `SchemaUpdatedEvent`. Those pairs are dropped here, decided by the same scoper both sides run over candidates from the same gather. Only a pair the gather returned may be dropped; one it missed keeps an imprecise read set and stays in the pass. The send is checked: `PostMergeDispatcher` scopes the pass only after the schema event went out. What nothing checks is that `computed_attribute_setup_python` reached its submission. That flow has no retry, so a failure there leaves the dropped pairs stale until the next change touches them.

Two costs come with this family, both on the coalesced path only. The read-set index is read after
`wait_for_schema_to_converge`, which scans the worker keys in the cache; the order is deliberate,
because a worker behind on the schema declares no Python attribute and reordering would read as
nothing to do. And the index is rebuilt for every flow run, including the levels of a chain, since
nothing that survives a process moves when a transform query is edited.

`process_transform` recomputes the one attribute it is asked for. A kind with several Python attributes gets one submission per attribute, so processing the whole kind per submission would run each transform once per attribute.

While the switch is on, the two Python per-node automations match `live` only, so a merge, a rebase and a coalesced write start no per-node flow. That is also what removes the two echo loops: the coalesced Jinja2, display-label and HFID writes carry the `recompute` origin and no longer re-fire the Python automations, and no `process_transform` runs during a merge to write `live` events back into the paths the merge suppressed.

That duplicate is load-bearing in one place. When the derivation of this family raises, the pass logs it and drops the family rather than letting the failure cancel the three schema-derived ones, which is the only place here that does less work rather than more. It is safe only because those automations still cover it. Gating them on the `live` origin removes that cover, so the same change has to make that fallback widen to the whole kind instead of dropping the family. A component test on the built trigger definitions asserts the Python ones carry no origin match, and fails as soon as the gate lands.

## Node mutation origin

Every node mutation event carries an `origin` label (`infrahub.node.origin`), one of:

| Origin | Set by | Meaning |
|--------|--------|---------|
| `live` | default | A direct edit through the API. |
| `merge` | the merge post-process | A replay of a merged change. |
| `rebase` | the rebase flow | A replay of a rebased change. |
| `recompute` | the bulk writer on a coalesced pass | A derived-value recompute write. |

The four families' cross-node triggers match only `live`, so `merge`, `rebase`, and `recompute` events do not start their per-node flows. This is what lets the coalesced pass be the single dispatcher for those families without double-processing. Other consumers (user action rules, webhooks, profiles) keep receiving every event whatever the origin.

**Location:** `events/constants.py` (`NodeMutationOrigin`, `NODE_ORIGIN_LABEL`); the `live`-only match is set in each family's trigger builder (`computed_attribute/models.py`, `display_labels/models.py`, `hfid/models.py`). The two Python builders apply it only while their pass is enabled.

## The bulk writer

**Location:** `core/recompute/bulk_write.py` (`BulkRecomputeWriter`), driven through `core/recompute/dispatch.py` (`BulkRecomputeDispatcher`)

The process flows render the new values, keep only the ones that differ from the stored value, and hand them to a `BulkRecomputeDispatcher` (wired by `build_bulk_recompute_dispatcher`). This is the single write path for all four families, on both the live and the coalesced side. The `coalesced` argument of the factory is the difference, and it is settled before the dispatcher exists: a live single-node recompute builds one with no chain (stamp `live`, let the emitted events carry any further readers), while a merge, rebase, or chained level builds one with a chain (stamp `recompute`, drive the next level here). Holding a chain is what makes a pass coalesced, so the two cannot disagree.

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
| `core/merge/recompute_coalescing.py` | `CoalescedRecomputeBuilder`, `CoalescedRecomputeSubmitter`, `MergeRecomputeCoordinator`, `RecomputeChainSubmitter`, `PythonTargetResolver`, `max_recompute_chain_depth` |
| `core/merge/python_target_resolution.py` | `IndexedPythonTargetResolver`: maps a change signature to the affected Python `(kind, attribute)` pairs and their node ids |
| `core/merge/python_target_sources.py` | The read-set and subscriber sources behind that resolver, and the factory the switch selects |
| `display_labels/scoping.py`, `hfid/scoping.py` | `derive_display_label_targets` / `derive_hfid_targets`: the builder's derivation step, mapping a changed `(kind, field)` set to the display-label and HFID values it affects (computed attributes use `computed_attribute/scoping.py`) |
| `core/recompute/bulk_write.py` | `BulkRecomputeWriter`, `AttributeValueWrite`, `WrittenNode` |
| `core/recompute/dispatch.py` | `BulkRecomputeDispatcher`, `build_bulk_recompute_dispatcher` (bulk write, then chain on a coalesced pass) |
| `core/merge/post_merge.py` | Merge: stamp `merge` origin, build and submit on the destination branch |
| `core/branch/tasks.py` | Rebase: stamp `rebase` origin, build and submit on the user branch |
| `events/constants.py` | `NodeMutationOrigin`, `NODE_ORIGIN_LABEL` |
| `computed_attribute/tasks.py`, `display_labels/tasks.py`, `hfid/tasks.py` | The four process flows that render values and call `BulkRecomputeDispatcher.dispatch`, two of them in the computed-attribute module |

## See Also

- [Computed Attributes](computed-attributes.md) - the live evaluation paths for Jinja2 computed attributes
- [Display Labels & HFID](display-labels-and-hfid.md) - the same for display labels and human-friendly ids
- [Selective Post-Merge Regeneration](selective-merge-regeneration.md) - the sibling merge-followup path for generators and artifacts
- [Events System](events.md) - node mutation events and the `origin` metadata
- [Merge Failure Recovery](merge-failure-recovery.md) - reversing a merge that died before the post-`MERGED` recompute
