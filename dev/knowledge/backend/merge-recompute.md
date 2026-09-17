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

`INFRAHUB_COALESCE_PYTHON_RECOMPUTE_AFTER_MERGE` is a temporary escape hatch for the dev cycle and a later PR removes it. While it is here it governs the family, on by default, and it governs **both halves at once**: the real resolver against an inert one, and whether the two Python trigger types carry the `live` origin filter. Keep the two halves on the same switch: with the filter applied and the resolver inert, nothing would recompute a replayed change.

The two halves do not land together. The resolver reads the setting per pass, while the filter is baked into the stored Prefect automation, which only a schema change, a branch deletion, a transform edit or `trigger_configure_all` rebuilds. So every worker has to carry the new value before any reconcile runs: a mixed fleet keeps re-flipping the stored automations, and until a reconcile lands the automations still hold the previous position.

The derivation applies the same per-action rules as the other families: a created node is its own target, an update selects the readers of the changed fields and, when the updated node is of the target kind, that node itself, a deletion selects the readers too. On top of that:

- **Read sets come from the analyzed transform queries.** A field the query does not read selects nothing. Imprecision is held per kind, so a query reading a derived field of one kind still rejects an unread field of another.
- **A query that is not pinned to a single object resolves no readers.** It keeps its read set, so a change to a kind it never reads selects nothing beyond the self-target rule below, and the schema-scoped backfill scopes a schema change on exactly the same read set. Inside a kind it reads, no field filter holds: the read set carries the fields the query selects and never the ones it only filters on, so a change to a filtered field moves a node into or out of the result while the members already in it stay untouched. Which nodes read it cannot be established either way, because readers come from query-group membership, which records what the last run read and never what the next one would. A created node is invisible to the existing subscribers and a deleted one leaves no membership behind. So any change to a kind it reads widens the attribute to its whole kind instead of resolving nodes, creations included. A created node of the attribute's own kind is still its own target when the query does not read that kind: nothing the query reads moved, so the new node's value is all there is to compute. The artifact and generator selector guards the same case by regenerating every target.
- **Readers come from the query-group subscriber index**, one union query per set of changed ids, never one per changed node.
- **An updated node of the target kind is also a target of its own**, next to the reader lookup. The reverse index only reaches a node that computed successfully at least once, since that is when it subscribed; a node whose first compute failed would otherwise keep a stale value after its own read field is merged. This is what makes the pass cover everything the owner automation covered.
- **A deleted node id is resolved in a lookup of its own.** Sharing one with live ids empties the whole result, which would drop the readers of the live changes. A deleted node holds no open membership edge any more, so its own lookup answers nothing; a reader that pointed at it is carried by its own relationship update, which the change set holds.
- **Every signal that cannot be narrowed widens to the whole target kind**, and is logged. An undeterminable read set, a query whose root is not pinned to one object, and a failed reader lookup all widen, creations included for the first two. One case is not a signal of that sort: an attribute whose transform is missing from the database is left out of the pass entirely. Nothing can compute it until the transform arrives, the recompute that follows the transform being created is what covers it then, and the schema-scoped backfill leaves it out for the same reason, since both build their candidates from the same gather. Widening it instead submits flows that raise `Unable to fetch transform`. A gather that fails outright is different: nothing is known about any attribute, so all of them widen. A widened target carries no node ids and goes to `trigger_update_python_computed_attributes` instead of `computed_attribute_process_transform`; the `whole_kind` flag is what carries that case to the submission planner, since chunking an empty id set would produce no submission at all.
- **A schema-changing merge already refreshes what its own scope selects**, one whole kind at a time, through `SchemaUpdatedEvent`. Those pairs are dropped here, decided by the same scoper both sides run over candidates from the same gather. Only a pair the gather returned may be dropped. When the gather fails outright, no pair may be dropped: every one carries an imprecise read set and stays in the pass. The send is checked: `PostMergeDispatcher` scopes the pass only after the schema event went out. What nothing checks is that `computed_attribute_setup_python` reached its submission. That flow has no retry, and the origin gate means no per-node automation answers the merge either, so a failure there leaves the dropped pairs stale until the next change touches them. Dropping them is still right: the duplicate has to come off the coalesced side, never off the schema side.

Two costs come with this family, both on the coalesced path only. A branch that declares no Python
attribute returns before `wait_for_schema_to_converge`, so it pays none of that wait, which costs
its full timeout whenever no worker publishes a schema hash. A branch that declares one waits, then
reads its read sets from the converged registry, because a worker behind on the schema reports
fewer attributes than the branch holds. The early return trusts the local registry on "declares
none". And the index is rebuilt for every flow run, including the levels of a chain, since nothing
that survives a process moves when a transform query is edited.

`process_transform` recomputes the one attribute it is asked for. A kind with several Python attributes gets one submission per attribute, so processing the whole kind per submission would run each transform once per attribute.

While the switch is on, the two Python trigger types match `live` only, so a merge, a rebase and a coalesced write start no per-node flow. That is also what removes the two echo loops: the coalesced Jinja2, display-label and HFID writes carry the `recompute` origin and no longer re-fire the Python automations, and a merge starts `process_transform` only through the coalesced pass, which passes `coalesced=True`, so those writes carry the `recompute` origin and none of them carry `live` back into the suppressed paths. A schema-changing merge is the exception: the schema-scoped backfill submits its whole-kind refresh without that flag, so those writes are stamped `live` and do re-enter those paths.

Group membership is refreshed by the recompute itself, not separately. Every read of a transform query passes `update_group=True`, and the API submits one `update_graphql_query_group` flow per request, which upserts the query group and adds the subscriber. The coalesced flow reads once per node in its batch, so a merge touching N nodes of a Python-attribute kind upserts N groups. An upgraded stack whose Python automations have not been reconciled yet is still in that state: the pass runs and the stored automations carry no origin filter, so the merge replay adds its own per-node flows and the upserts are about 2N until the reconcile lands.

When the resolution of this family raises, the pass logs it and widens every declared Python attribute to its whole kind, rather than letting the failure cancel the three schema-derived submissions. It cannot drop the family instead: the per-node automations no longer answer a replayed change, so nothing else would refresh those values. The widened set comes from the schema, so it can include an attribute whose transform is missing, and those flows raise; a failed resolution is the one place that accepts that, because nothing is known about which transforms exist.

## Node mutation origin

Every node mutation event carries an `origin` label (`infrahub.node.origin`), one of:

| Origin | Set by | Meaning |
|--------|--------|---------|
| `live` | default | A direct edit through the API. |
| `merge` | the merge post-process | A replay of a merged change. |
| `rebase` | the rebase flow | A replay of a rebased change. |
| `recompute` | the bulk writer on a coalesced pass | A derived-value recompute write. |

The four families' cross-node triggers match only `live`, the Python ones while `INFRAHUB_COALESCE_PYTHON_RECOMPUTE_AFTER_MERGE` is on, so `merge`, `rebase`, and `recompute` events do not start their per-node flows. This is what lets the coalesced pass be the single dispatcher for those families without double-processing. Other consumers (user action rules, webhooks, profiles) keep receiving every event whatever the origin.

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
