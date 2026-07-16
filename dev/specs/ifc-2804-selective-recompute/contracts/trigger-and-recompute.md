# Contract: Trigger match, transform->attributes resolution, and recompute fan-out

Authoritative, field-level contract for the three internal boundaries of this feature.
Every value below is taken from real code; file:line references point at the source of
each shape. No new external API is introduced; these are internal Prefect-automation and
workflow contracts.

Constants referenced:

- `InfrahubKind.TRANSFORMPYTHON == "CoreTransformPython"` (`core/constants/infrahubkind.py:86`)
- `NODE_ORIGIN_LABEL == "infrahub.node.origin"` (`events/constants.py:5`)
- `NodeMutationOrigin.LIVE.value == "live"` (`events/constants.py:8`)
- `NodeCreatedEvent.event_name == "infrahub.node.created"` (`events/node_action.py:161`)
- `NodeUpdatedEvent.event_name == "infrahub.node.updated"` (`events/node_action.py:169`)
- `NodeDeletedEvent.event_name == "infrahub.node.deleted"` (`events/node_action.py:177`)

## 1. Event -> trigger match shape

### 1.1 Create trigger

```python
EventTrigger(
    events={NodeCreatedEvent.event_name},
    match={
        "infrahub.node.kind": InfrahubKind.TRANSFORMPYTHON,
        NODE_ORIGIN_LABEL: NodeMutationOrigin.LIVE.value,
    },
    # no match_related: a create is itself the signal to compute for the first time
)
```

Fires when a `CoreTransformPython` node is created by a live edit (the import write, which
is origin=LIVE). Does not fire on merge/rebase replay of a create (origin != live).

### 1.2 Update trigger

```python
EventTrigger(
    events={NodeUpdatedEvent.event_name},
    match={
        "infrahub.node.kind": InfrahubKind.TRANSFORMPYTHON,
        NODE_ORIGIN_LABEL: NodeMutationOrigin.LIVE.value,
    },
    match_related={
        "prefect.resource.role": ["infrahub.node.attribute_update"],
        "infrahub.field.name": ["fingerprint"],
    },
)
```

Mirrors the data-path shape (`computed_attribute/models.py:165-175`), narrowed to the
single `fingerprint` field. Fires only when a live edit changes the transform's
`fingerprint` attribute. The related resource carrying
`infrahub.field.name == "fingerprint"` is emitted by `get_related()`
(`node_action.py:35-50`) only when `fingerprint` is in the changelog, so an unchanged
fingerprint on re-import produces no match (SC-004, US1, US3).

### 1.3 Delete trigger

```python
EventTrigger(
    events={NodeDeletedEvent.event_name},
    match={
        "infrahub.node.kind": InfrahubKind.TRANSFORMPYTHON,
        NODE_ORIGIN_LABEL: NodeMutationOrigin.LIVE.value,
    },
)
```

Fires when a `CoreTransformPython` node is deleted by a live edit. The delete workflow is
NOT a no-op: it runs the data-path (node-input) automation reconciliation (section 3.5), so
the removed transform's node-input automation is dropped by `setup_triggers`' `to_delete`
diff (research Decision 5). It does not fan out a recompute (the transform is gone).

### 1.4 Match semantics (why each clause is load-bearing)

| Clause                                   | Requirement it satisfies | Mechanism |
|------------------------------------------|--------------------------|-----------|
| `infrahub.node.kind == CoreTransformPython` | FR-018 (scope), FR-013 (loop) | A recompute write targets the attribute's own node kind, never the transform kind, so it cannot match. |
| `NODE_ORIGIN_LABEL == live`              | FR-012 (no merge/rebase double-fire) | Merge stamps MERGE, rebase stamps REBASE; neither matches `live`. |
| `field.name == fingerprint` (update)     | FR-008 (fingerprint-only) | Other attribute edits on the transform emit a different `field.name` and do not match. |

**Correction to the epic's assumption.** The epic states loop safety comes from a
`RECOMPUTE` origin. There is no `RECOMPUTE` value in `NodeMutationOrigin`
(`events/constants.py:8`), and the recompute write is stamped `LIVE`
(`graphql/mutations/computed_attribute.py:122`). Loop safety is provided by the
**kind + field** match, not by origin. Origin=LIVE is still required, but for the
merge/rebase case only.

## 2. Event payload fields consumed by the workflow

From `NodeMutatedEvent.get_resource()` (`node_action.py:146`):

| Payload path                                  | Used for |
|-----------------------------------------------|----------|
| `event.resource['infrahub.node.id']`          | resolve the transform node -> its name |
| `event.resource['infrahub.branch.name']`      | branch to resolve schema and to fan out on |
| `event.payload['context']`                    | `EventContext` threaded into recompute (account id, etc.) |

Passed as `ExecuteWorkflow.parameters` using `jinja_parameter(...)`
(`trigger/models.py:213`) for string values and the `__prefect_kind: json` wrapper for the
context object, exactly as the existing triggers do (`triggers.py:19-26`,
`models.py:258-272`).

## 3. Transform -> attributes resolution contract

Input: `(branch_name, transform_id)`. Output: `list[PythonDefinition]`.

```text
1. Resolve transform_id -> the transform node on branch_name, via client.get with
   raise_when_missing=False. If the node is not found (a branch race, or a delete that has
   already landed), log and SKIP the recompute leg, but still reconcile (section 3.5). This
   is the over-regenerate-never-under-regenerate fallback: an unresolved transform never
   silently drops the reconciliation.

2. schema_branch = registry.schema.get_schema_branch(name=branch_name)
   mapping = schema_branch.computed_attributes.python_attributes_by_transform   # facade.py:56
   # A computed attribute may wire its transform by NAME or by UUID
   # (core/schema/computed_attribute.py documents "name or ID"; the mapping is keyed by that
   # raw value at python_transform.py). UNION both keys and dedupe by (kind, attribute name),
   # so a transform wired by name for one attribute and by id for another recomputes both:
   definitions = dedupe(mapping.get(transform_name, []) + mapping.get(transform_id, []))

3. definitions is [] only when the transform feeds no computed attribute
   (edge case "Transform feeding no computed attribute"). The empty result returns before any
   client.all node fetch (section 4): inert, no recompute, no node read. Reconciliation
   (section 3.5) still runs regardless.
```

Guarantees:

- **Name-or-id (FR-010, SC-011):** the lookup checks both the transform's name and its id,
  so a computed attribute that wires its transform by UUID resolves to the same attribute(s)
  as one that wires it by name.
- **Cheap empty path (D7, SC-010):** a transform feeding no computed attribute resolves to
  `[]` from the id/name + dict lookup alone and returns before any `client.all` node fetch.
- **Scoping (FR-009):** the mapping entry contains only the attributes fed by that one
  transform. No other transform's attributes are reachable from this key.
- **Multiplicity (US2 sc.4):** a transform feeding N attributes yields N `PythonDefinition`
  entries; all are recomputed, none outside the set.
- **Determinism:** the mapping is derived from current schema state, so a deleted or
  renamed transform resolves to `[]` (US5 safety).

## 3.5 Data-path (node-input) reconciliation contract

On **every** lifecycle event (create / update / delete), the workflow reconciles the
data-path automations that recompute an attribute when a node feeding the transform's query
changes. This is the duty the removed commit trigger performed as a side effect; the
lifecycle flow now owns it (research Decision 5). Each trigger type is gathered and applied
under its trigger-registry lock via `setup_triggers_specific`, which gathers the desired set
*inside* the lock so a concurrent reconcile cannot apply a stale set and delete an automation
another run just created:

```python
await setup_triggers_specific(gatherer=_gather_computed_attr_python_triggers,
                              trigger_type=TriggerType.COMPUTED_ATTR_PYTHON, db=db)
await setup_triggers_specific(gatherer=_gather_computed_attr_python_query_triggers,
                              trigger_type=TriggerType.COMPUTED_ATTR_PYTHON_QUERY, db=db)
```

- **On create / update:** builds or refreshes the node-input automation for the transform,
  so a transform-only import (no schema diff, so the schema path never runs) never leaves it
  unbuilt.
- **On delete:** the gathered desired set no longer contains the removed transform, so
  `setup_triggers`' `to_delete = set(existing) - set(desired)` diff (`trigger/setup.py`)
  drops its automation.
- **Concurrency:** the gather-and-apply runs inside the per-type lock (namespace
  `trigger-rules`), so overlapping lifecycle and schema-path reconciles serialize instead of
  racing on the same automation set.

This is more precise than the removed commit sweep: it runs on transform events only, not on
every commit. The schema path (`computed_attribute_setup_python`) shares the same locked
reconciliation on schema change.

## 4. Recompute fan-out contract

For each `PythonDefinition` in the resolution result (create and update-of-fingerprint only),
submit the **existing** `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` workflow (unchanged). The
`context` (`EventContext`) MUST be passed in BOTH `submit_workflow(context=...)` and in
`parameters`, because the fan-out flow requires a `context` parameter (`tasks.py:221-226`) and
fails at runtime without it (existing callers pass it both ways):

```python
await get_workflow().submit_workflow(
    workflow=TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,   # catalogue.py:414
    context=context,
    parameters={
        "branch_name": branch_name,
        "computed_attribute_name": definition.attribute.name,
        "computed_attribute_kind": definition.kind,
        "context": context,   # required by trigger_update_python_computed_attributes (tasks.py:221-226)
    },
)
```

That workflow (`tasks.py:221`) then:

```text
nodes = await get_client().all(kind=definition.kind, branch=branch_name)   # tasks.py:229
object_ids = [n.id for n in nodes]
for chunk in _chunk_ids(object_ids, get_submission_chunk_size()):          # tasks.py:236
    submit COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM(branch, kind, chunk, name, kind, context)
```

Guarantees:

- **All nodes of the kind (FR-004):** `client.all(kind=...)` returns every node of the
  attribute's kind on the branch; each is recomputed.
- **Reuse (spec Assumption "per-node recompute reused unchanged"):** the per-node compute
  (`process_transform_for_node`, `tasks.py:94`) is untouched.
- **No loop (FR-013):** the per-node write goes to `definition.kind` (e.g. `TestingCar`),
  emitting a `NodeUpdatedEvent` with `kind=TestingCar`, which does not match the
  transform-scoped trigger.

## 5. Contrast with the removed commit path

| Aspect            | Removed commit path (`triggers.py:10`)        | New lifecycle path                          |
|-------------------|-----------------------------------------------|---------------------------------------------|
| Trigger event     | `CommitUpdatedEvent` (any repo commit)        | `NodeCreated/Updated/DeletedEvent` on transform |
| Scope decision    | `computed_attribute_setup_python`, `changed_elements=None` -> `fallback_full_recompute=True` selects ALL (`scoping.py:132`) | resolution yields ONLY the changed transform's attributes |
| Fan-out breadth   | every transform-based attribute on the branch | only the attributes fed by one transform    |
| Also does         | reconciles data-path automations via `setup_triggers` on every commit | reconciles data-path automations via `setup_triggers` on every transform create/update/delete (same coverage, fewer runs) |
| Recompute fires on | every commit, related or not                  | create, and update when a fingerprint actually changes |
| Reconcile fires on | every commit                                  | every transform create / update / delete    |

The schema-driven `computed_attribute_setup_python` (via
`TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA`) keeps its `changed_elements` scoping and its
`setup_triggers` reconciliation. Only the commit-event entry point into it is removed; the
reconciliation it did as a side effect is now owned by the lifecycle flow (section 3.5), so
removing the commit trigger does NOT drop the data-path reconciliation.
