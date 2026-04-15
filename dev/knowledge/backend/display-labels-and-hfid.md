# Display Labels and Human-Friendly IDs

> Part of: `dev/knowledge/backend/` | Related: [mutations.md](mutations.md), [architecture.md](architecture.md)

Display labels and HFIDs are computed node properties. Display labels use Jinja2 templates; HFIDs use schema path lists.
## Schema Definition

On `BaseNodeSchema`:

- **`display_label`**: Jinja2 template string (e.g., `"{{ name__value }} {{ color__name__value }}"`)
- **`human_friendly_id`**: List of schema paths (e.g., `["name__value", "owner__name__value"]`)
- **`display_labels`** (deprecated): Legacy list format, auto-converted to `display_label` during schema processing

Schema paths use `__` separators: `color__name__value` means "follow the `color` relationship, read the `name` attribute's `value` property."

## Key Classes

### NodePropertyAttribute subclasses

**Location:** `backend/infrahub/core/node/node_property_attribute.py`

- **`DisplayLabel`**: Wraps a Jinja2 `display_label` template
- **`HumanFriendlyIdentifier`**: Wraps an HFID path list

Both provide:

| Method | Purpose |
|--------|---------|
| `analyze_variables()` | Parses template to extract attribute/relationship dependencies |
| `compute(db, node)` | Resolves variables via `node.get_path_value()`, renders template |
| `needs_update(fields)` | Returns True if any dependent field changed |
| `set_value(value, manually_assigned)` | Manual override; skips future `compute()` calls |

### HFID Storage and Indexing

**Location:** `backend/infrahub/core/attribute.py`

HFID values are stored using `IndexedListAttribute`, a subclass of `ListAttributeOptional` that:

- Returns `AttributeDBNodeType.INDEXED` from `get_db_node_type()`, so the `AttributeValue` node gets the `AttributeValueIndexed` label in Neo4j (enabling RANGE/TEXT index lookups)
- Falls back to non-indexed storage (`DEFAULT`) with a warning when the serialized value exceeds `MAX_STRING_LENGTH` (4096 bytes). These oversized HFIDs are still saved but are not retrievable via `get_one_by_hfid`.

`HumanFriendlyIdentifier.compute()` converts all resolved path values to strings via `str()`. This ensures consistent JSON serialization — callers, the GraphQL API, and the stored value all use `list[str]`.

### HFID Lookup

**Location:** `backend/infrahub/core/manager.py`, `backend/infrahub/core/query/node.py`

`NodeManager.get_one_by_hfid()` uses `NodeGetByHFIDQuery` to match directly on the stored `human_friendly_id` attribute value. The query starts from `AttributeValueIndexed` nodes matching the serialized HFID, traverses back to the owning node, and branch-filters each edge (`IS_PART_OF`, `HAS_ATTRIBUTE`, `HAS_VALUE`). Because the query only matches indexed values, HFIDs exceeding `MAX_STRING_LENGTH` are not searchable.

### Schema Registries

**Location:** `backend/infrahub/core/schema/schema_branch_display.py`, `schema_branch_hfid.py`

Each registry stores per-kind definitions with:

- **`attributes`**: Direct attribute dependencies (e.g., `{"name"}`)
- **`relationships`**: Relationship names referenced (e.g., `{"color"}`)
- **`relationship_fields`**: Map of relationship name to peer attribute names (e.g., `{"color": {"name"}}`)

Registries also maintain **`RelationshipTriggers`** -- inverse mappings for recomputation when a peer's attribute changes.

Registration happens during schema processing: display labels are registered inside `SchemaBranch.validate_display_label()`, and HFIDs are registered via `SchemaBranch.register_human_friendly_id()` (a separate step from `process_human_friendly_id()`, both called from `process_post_validation()`).

## resolve_relationships() and extra_filters

**Location:** `Node.resolve_relationships()` and `Node._collect_extra_filters()` in `backend/infrahub/core/node/__init__.py`

When a node's display label or HFID template references relationship peer attributes (e.g., `color__name__value`), those attributes must be loaded during `Relationship.resolve()`. The `resolve_relationships()` method calls `_collect_extra_filters()`, which reads `relationship_fields` from the registries and builds the filter map. These are then passed as `extra_filters` to each `RelationshipManager.resolve()`.

```
resolve_relationships()
  -> _collect_extra_filters()
       -> read relationship_fields from schema_branch.hfids / schema_branch.display_labels
       -> build extra_filters: {"color": {"name"}, "owner": {"family_name"}}
  -> for each RelationshipManager:
       relm.resolve(db, fields=extra_filters[rel_name])
         -> Relationship.resolve() loads peer with those fields populated
```

### Guard Conditions

In `_collect_extra_filters()`, extra filters are computed for three sources:

```python
if not self._existing or self._human_friendly_id:
    # Fetch HFID-related peer attributes
if not self._existing or self._display_label:
    # Fetch display-label-related peer attributes
if self._existing:
    # Fetch peer attributes needed by Jinja2 computed attribute templates
```

- **New nodes** (`not self._existing`): Always need HFID/display_label extra filters
- **Existing nodes with HFID/display_label set**: Need extra filters for recomputation during updates
- **Existing nodes (updates)**: Always include peer attributes needed by Jinja2 computed attribute templates (via `computed_attributes.get_registered_jinja2_node`)

## Lifecycle

### Create

1. `Node.new()` -> `_process_fields()` -> `_process_fields_relationships()` (creates RelationshipManagers)
2. `Node.save()` -> `resolve_relationships()` (loads peers with extra_filters) -> `_create()`
3. `_create()` -> `add_human_friendly_id()` / `add_display_label()` (compute and persist)

**Note:** `NodeCreateAllQuery` (`core/query/node.py` ~lines 169-180) routes HFID and display_label attributes based on their `get_db_node_type()`. The `IndexedListAttribute` used for HFID returns `INDEXED` when within size limits, so the value lands in the `attributes_indexed` bucket and gets the `AttributeValueIndexed` label. Oversized values fall back to `DEFAULT` (no index).

### Update

1. `Node.load()` receives `human_friendly_id` and `display_label` kwargs, wraps them in property objects
2. `Node.save()` -> `resolve_relationships()` (extra_filters gated by `self._human_friendly_id` / `self._display_label` for those sources, plus always-on computed attribute extra filters via `computed_attributes.get_registered_jinja2_node`)
3. `_update()` checks `needs_update(fields)` for each property; recomputes and persists if needed

### Query-Time Resolution (`get_display_label`)

`Node.get_display_label(db)` returns the display label for a node during GraphQL queries. It distinguishes between saved and virtual nodes:

1. **Stored value exists** (`_display_label` set with a non-empty value): return it directly.
2. **Stored attribute is empty** (`_display_label` set but value is null): return `""`. The async backfill workflow is responsible for populating stored values after schema changes. Computing on the fly here would cause the backfill to detect no difference and skip the update.
3. **No `display_label` template** in schema: return `repr(self)`.
4. **No stored attribute at all** (virtual nodes like IPAM available nodes that are never saved): compute on the fly using `DisplayLabel.compute()`.

### Async Backfill After Schema Changes

When a schema is updated to add or change a `display_label`, the async Prefect workflow chain updates existing nodes:

```
SchemaUpdatedEvent
  -> display_labels_setup_jinja2 (gathers triggers, detects new/changed templates)
  -> trigger_update_display_labels (iterates all nodes of the kind)
  -> process_display_label (queries node via GraphQL, renders template)
  -> display_label_jinja2_update_value (compares rendered vs stored, writes if different)
```

The trigger definitions and gathering logic live in `backend/infrahub/display_labels/`.

### Manual Override

`set_display_label(value)` and `set_human_friendly_id(value)` set `manually_assigned=True`, which causes `compute()` to no-op on future calls.


## Hierarchical Relationships and Inline Fragments

When a display label, HFID, or computed attribute template references an attribute through a hierarchical relationship (e.g., `parent__name__value`), the GraphQL query must use an **inline fragment** to access attributes that exist on the concrete peer type but not on the hierarchical generic.

**Why:** A hierarchical relationship's GraphQL type resolves to the generic (e.g., `LocationGeneric`), not the concrete peer (e.g., `LocationSite`). Attributes defined only on the concrete type are not queryable directly — they require `... on LocationSite { name { value } }`.

**Condition:** `relationship.hierarchical and relationship.peer != relationship.hierarchical`

This logic lives in the `query_fields` property of all three GraphQL model classes:

- `ComputedAttrJinja2GraphQL` in `computed_attribute/models.py`
- `DisplayLabelJinja2GraphQL` in `display_labels/models.py`
- `HFIDGraphQL` in `hfid/models.py`

Example generated query structure:

```graphql
# Without hierarchy (peer == type):
parent { node { name { value } } }

# With hierarchy (peer != generic):
parent { node { ... on LocationSite { name { value } } } }
```

## Key Files

| File | What |
|------|------|
| `core/attribute.py` | `IndexedListAttribute` (HFID storage with indexing and size fallback) |
| `core/node/node_property_attribute.py` | `DisplayLabel`, `HumanFriendlyIdentifier` classes |
| `core/node/__init__.py` | `resolve_relationships()`, `_collect_extra_filters()`, `add_display_label()`, `_update()` |
| `core/query/node.py` | `NodeGetByHFIDQuery` (branch-aware HFID lookup) |
| `core/manager.py` | `NodeManager.get_one_by_hfid()` (uses `NodeGetByHFIDQuery`) |
| `core/schema/schema_branch_display.py` | `DisplayLabels` registry, `TemplateLabel` |
| `core/schema/schema_branch_hfid.py` | `HFIDs` registry, `HFIDDefinition` |
| `core/schema/schema_branch.py` | `validate_display_label()`, `process_human_friendly_id()` |
| `core/schema/basenode_schema.py` | `SchemaAttributePath` (parsed template variables) |
| `display_labels/models.py` | `DisplayLabelJinja2GraphQL` (GraphQL query generation) |
| `hfid/models.py` | `HFIDGraphQL` (GraphQL query generation) |
| `computed_attribute/models.py` | `ComputedAttrJinja2GraphQL` (GraphQL query generation) |
| `graphql/mutations/display_label.py` | Manual display_label override mutation |
