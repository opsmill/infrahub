# Display Labels and Human Friendly IDs

> Part of: `dev/knowledge/backend/` | Related: [mutations.md](mutations.md), [architecture.md](architecture.md)

Display labels and HFIDs are computed node properties backed by Jinja2 templates (display labels) or schema path lists (HFIDs). They depend on attributes and relationship peer attributes, requiring special handling during relationship resolution.

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

In `_collect_extra_filters()`, extra filters are only computed when needed:

```python
if not self._existing or self._human_friendly_id:
    # Fetch HFID-related peer attributes
if not self._existing or self._display_label:
    # Fetch display-label-related peer attributes
```

- **New nodes** (`not self._existing`): Always need extra filters
- **Existing nodes with HFID/display_label set**: Need extra filters for recomputation during updates

## Lifecycle

### Create

1. `Node.new()` -> `_process_fields()` -> `_process_fields_relationships()` (creates RelationshipManagers)
2. `Node.save()` -> `resolve_relationships()` (loads peers with extra_filters) -> `_create()`
3. `_create()` -> `add_human_friendly_id()` / `add_display_label()` (compute and persist)

### Update

1. `Node.load()` receives `human_friendly_id` and `display_label` kwargs, wraps them in property objects
2. `Node.save()` -> `resolve_relationships()` (extra_filters gated by `self._human_friendly_id` / `self._display_label`)
3. `_update()` checks `needs_update(fields)` for each property; recomputes and persists if needed

### Manual Override

`set_display_label(value)` and `set_human_friendly_id(value)` set `manually_assigned=True`, which causes `compute()` to no-op on future calls.


## Key Files

| File | What |
|------|------|
| `core/node/node_property_attribute.py` | `DisplayLabel`, `HumanFriendlyIdentifier` classes |
| `core/node/__init__.py` | `resolve_relationships()`, `_collect_extra_filters()`, `add_display_label()`, `_update()` |
| `core/schema/schema_branch_display.py` | `DisplayLabels` registry, `TemplateLabel` |
| `core/schema/schema_branch_hfid.py` | `HFIDs` registry, `HFIDDefinition` |
| `core/schema/schema_branch.py` | `validate_display_label()`, `process_human_friendly_id()` |
| `core/schema/basenode_schema.py` | `SchemaAttributePath` (parsed template variables) |
| `display_labels/models.py` | `DisplayLabelJinja2GraphQL` (GraphQL query generation) |
| `graphql/mutations/display_label.py` | Manual display_label override mutation |
