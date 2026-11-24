# Phase 1 Data Model: Selective Recompute of Transform-Based Computed Attributes

This feature adds **no database schema**. The `fingerprint` attribute already exists on
`CoreTransformation` (inherited by `CoreTransformPython`), delivered by IFC-2844 and
present in `backend/infrahub/core/protocols.py` as `fingerprint: StringOptional`
(one entry per fingerprinted kind, lines 214/310/401/435). The entities below are the
**in-memory and event data shapes** the recompute mechanism reads and produces. Nothing
here is persisted beyond what already exists.

## Existing schema entity consumed (not modified)

### `CoreTransformPython.fingerprint`

| Property    | Value                     | Source            |
|-------------|---------------------------|-------------------|
| `name`      | `fingerprint`             | IFC-2844          |
| `kind`      | `Text`                    | IFC-2844          |
| `optional`  | `True` (null permitted)   | IFC-2844          |
| `branch`    | `BranchSupportType.AWARE` | IFC-2844          |
| `read_only` | `False`                   | IFC-2844          |

This feature does **not** read the fingerprint's *value*. It reacts to the *event of the
value changing*. Null vs. non-null is therefore never inspected by feature code; a null->
value transition is just an attribute-change event like any other (see research Decision 6).

## Event data shapes consumed

The lifecycle triggers match on, and the fired workflow reads, fields produced by
`NodeMutatedEvent` (`backend/infrahub/events/node_action.py`).

### Resource (from `get_resource()`, `node_action.py:146`)

```text
prefect.resource.id     = "infrahub.node.<node_id>"
infrahub.node.kind      = "CoreTransformPython"        # matched by the trigger
infrahub.node.id        = "<transform node id>"        # read by the workflow
infrahub.node.action    = created | updated | deleted
infrahub.branch.name    = "<branch>"                   # read by the workflow
infrahub.node.origin    = live | merge | rebase        # matched by the trigger (LIVE)
```

`NODE_ORIGIN_LABEL == "infrahub.node.origin"` (`events/constants.py:5`).

### Related resource per changed attribute (from `get_related()`, `node_action.py:35`)

One entry per attribute in the changelog:

```text
prefect.resource.role   = "infrahub.node.attribute_update"   # matched
infrahub.field.name     = "fingerprint"                       # matched (update trigger)
infrahub.attribute.name = "fingerprint"
infrahub.attribute.value / value_previous / action           # not matched, available
```

The update trigger's `match_related` selects exactly the entry whose `infrahub.field.name`
is `fingerprint`. Because `get_related()` emits a related resource only for attributes
present in the changelog, a re-import that leaves the fingerprint unchanged emits **no**
`fingerprint` related resource and the trigger does not fire.

## In-memory resolution shapes (not persisted)

### `PythonDefinition` (`schema_branch_computed/python_transform.py:22`)

```python
@dataclass
class PythonDefinition:
    kind: str                 # the node kind carrying the computed attribute (e.g. TestingCar)
    attribute: AttributeSchema
    # key_name -> f"{kind}_{attribute.name}"
```

### `python_attributes_by_transform` (`facade.py:56` -> `python_transform.py:91`)

```text
dict[transform_name: str -> list[PythonDefinition]]
```

Built from the schema branch's registered Python computed attributes. Keyed by the
transform's **name** (the `computed_attribute.transform` value). This is the map the
lifecycle workflow uses to answer "which attribute(s) does this transform feed?". One
transform may feed several attributes (US2 scenario 4); one attribute is fed by exactly
one transform (spec Assumptions).

### Resolution result (transient, in the new workflow)

```text
transform node id  --(query by id)-->  transform name
transform name     --(python_attributes_by_transform)-->  [PythonDefinition, ...]
each PythonDefinition  -->  (branch_name, attribute.name, kind)  # fan-out key
```

## Trigger definitions (in-memory, registered at startup)

Three `BuiltinTriggerDefinition` objects, replacing the single removed commit trigger.
No branch dimension (builtin triggers are not branch-specific,
`trigger/models.py:119`). Shape summary; exact match dicts in
`contracts/trigger-and-recompute.md`.

| Trigger        | events                | key match            | match_related (field)   | workflow action                         |
|----------------|-----------------------|----------------------|-------------------------|-----------------------------------------|
| create         | `NodeCreatedEvent`    | kind, origin=LIVE    | (none / role-only)      | resolve + fan-out (first computation)   |
| update         | `NodeUpdatedEvent`    | kind, origin=LIVE    | role, field=fingerprint | resolve + fan-out (selective recompute) |
| delete         | `NodeDeletedEvent`    | kind (+origin=LIVE)  | (none)                  | reconcile node-input automations, dropping the removed transform's (see research Decision 5) |

`generate_name()` for a `BuiltinTriggerDefinition` is `f"builtin::{name}"`
(`trigger/models.py:285`, `:302`), reconciled in the `builtin_triggers` set.

## Workflow parameter shapes

### New lifecycle workflow (added)

`process_transform_lifecycle` (name illustrative), params from the event via
`jinja_parameter`:

```text
branch_name  <- {{ event.resource['infrahub.branch.name'] }}
transform_id <- {{ event.resource['infrahub.node.id'] }}
context      <- {{ event.payload['context'] | tojson }}   # json prefect-kind
```

### Reused fan-out workflow (unchanged)

`TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` (`catalogue.py:414`, `tasks.py:221`) params:

```text
branch_name             : str
computed_attribute_name : str
computed_attribute_kind : str
context                 : EventContext
```

Submitted once per `PythonDefinition` the transform feeds.

## What is removed

- `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` (`triggers.py:10`) and its entry in
  `builtin_triggers` (`trigger/catalogue.py:19`). This is the only data-shape removal.

## Relationship diagram

```text
                 (git import writes fingerprint via SDK, origin=LIVE)
                                    │
                       CoreTransformPython node
                     created / fingerprint updated / deleted
                                    │  NodeCreated/Updated/DeletedEvent
                                    │  (kind=CoreTransformPython, origin=LIVE,
                                    │   related field=fingerprint on update)
                                    ▼
                  ┌─────────────────────────────────────┐
                  │  static builtin lifecycle trigger    │  (create / update / delete)
                  └─────────────────────────────────────┘
                                    │  transform_id, branch_name
                                    ▼
                  ┌─────────────────────────────────────┐
                  │  process_transform_lifecycle (new)   │
                  │  id -> name -> python_attributes_by_ │
                  │  transform[name] -> [PythonDefinition]│
                  └─────────────────────────────────────┘
                                    │  one submit per PythonDefinition
                                    ▼
                  TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES (reused)
                     client.all(kind=attr.kind) -> chunk ids
                                    │
                                    ▼
                  COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM per chunk
                     (writes value to target node, origin=LIVE,
                      kind != CoreTransformPython -> never re-fires trigger)
```
