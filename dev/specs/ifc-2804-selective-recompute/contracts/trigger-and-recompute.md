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

Fires when a `CoreTransformPython` node is deleted by a live edit. Under the static-trigger
model there is no per-transform automation to remove, so this trigger's workflow is a
no-op/log (research Decision 5). Registered for symmetry and testability.

### 1.4 Match semantics (why each clause is load-bearing)

| Clause                                   | Requirement it satisfies | Mechanism |
|------------------------------------------|--------------------------|-----------|
| `infrahub.node.kind == CoreTransformPython` | FR-016 (scope), FR-011 (loop) | A recompute write targets the attribute's own node kind, never the transform kind, so it cannot match. |
| `NODE_ORIGIN_LABEL == live`              | FR-010 (no merge/rebase double-fire) | Merge stamps MERGE, rebase stamps REBASE; neither matches `live`. |
| `field.name == fingerprint` (update)     | FR-007 (fingerprint-only) | Other attribute edits on the transform emit a different `field.name` and do not match. |

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
1. Resolve transform_id -> transform name on branch_name.
   Reuse ComputedAttributeTransformQuery-style lookup by id (tasks.py:182 fetches a
   transform by id today). id -> name is a single GraphQL read.

2. schema_branch = registry.schema.get_schema_branch(name=branch_name)
   mapping = schema_branch.computed_attributes.python_attributes_by_transform   # facade.py:56
   definitions = mapping.get(transform_name, [])

3. definitions is [] when the transform feeds no computed attribute
   (edge case "Transform feeding no computed attribute" -> inert, no recompute).
```

Guarantees:

- **Scoping (FR-008):** `mapping[transform_name]` contains only the attributes fed by that
  one transform. No other transform's attributes are reachable from this key.
- **Multiplicity (US2 sc.4):** a transform feeding N attributes yields N `PythonDefinition`
  entries; all are recomputed, none outside the set.
- **Determinism:** the mapping is derived from current schema state, so a deleted or
  renamed transform resolves to `[]` (US5 safety).

## 4. Recompute fan-out contract

For each `PythonDefinition` in the resolution result, submit the **existing**
`TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` workflow (unchanged):

```python
await get_workflow().submit_workflow(
    workflow=TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,   # catalogue.py:414
    context=context,
    parameters={
        "branch_name": branch_name,
        "computed_attribute_name": definition.attribute.name,
        "computed_attribute_kind": definition.kind,
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
- **No loop (FR-011):** the per-node write goes to `definition.kind` (e.g. `TestingCar`),
  emitting a `NodeUpdatedEvent` with `kind=TestingCar`, which does not match the
  transform-scoped trigger.

## 5. Contrast with the removed commit path

| Aspect            | Removed commit path (`triggers.py:10`)        | New lifecycle path                          |
|-------------------|-----------------------------------------------|---------------------------------------------|
| Trigger event     | `CommitUpdatedEvent` (any repo commit)        | `NodeCreated/Updated/DeletedEvent` on transform |
| Scope decision    | `computed_attribute_setup_python`, `changed_elements=None` -> `fallback_full_recompute=True` selects ALL (`scoping.py:132`) | resolution yields ONLY the changed transform's attributes |
| Fan-out breadth   | every transform-based attribute on the branch | only the attributes fed by one transform    |
| Also does         | reconciles data-path automations via `setup_triggers` | recompute only; no automation reconciliation |
| Fires on          | every commit, related or not                  | only when a fingerprint actually changes    |

The schema-driven `computed_attribute_setup_python` (via
`TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA`) keeps its `changed_elements` scoping and its
`setup_triggers` reconciliation. Only the commit-event entry point into it is removed.
