# Data Model: Local Computation of Jinja2 Computed Attributes

No new entities, database tables, or schema changes are required. This feature modifies the runtime behavior of existing data structures.

## Modified Entities

### RegisteredNodeComputedAttribute (schema_branch_computed.py)

**Current fields**:
- `local_fields: dict[str, list[ComputedAttributeTarget]]` — maps field names to targets
- `relationships: dict[str, list[ComputedAttributeTarget]]` — maps relationship names to targets

**New computed property**:
- `relationship_fields: dict[str, set[str]]` — maps relationship names to the set of peer attribute names needed for template rendering. Derived from parsing the relationship entries' `ComputedAttributeTarget.attribute.computed_attribute.jinja2_template` variable paths. Used by `_collect_extra_filters()` to load peer attributes during `resolve_relationships()`.

### Node (_update flow)

**New runtime state** during `_update()`:
- List of `ComputedAttributeTarget` objects for locally-affected computed attributes (transient, not persisted)
- Recomputed attribute values saved via the same `attr.save()` mechanism used for regular attributes

### ComputedAttrJinja2TriggerDefinition (models.py)

**Behavioral change**: `from_computed_attribute()` skips creating Prefect automation triggers for `ComputedAttributeTriggerNode` entries where `targets_self=True`. These local triggers are handled inline instead.

## Relationships

No new relationships. The existing `computed_attribute` field on `AttributeSchema` and the `RegisteredNodeComputedAttribute` dependency graph are used as-is.

## State Transitions

No new state machines. The computed attribute value transitions from "stale" to "current" within the same mutation transaction (previously this happened asynchronously via background task).
