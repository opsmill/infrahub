# Computed Attributes (Jinja2)

> Part of: `dev/knowledge/backend/` | Related: [display-labels-and-hfid.md](display-labels-and-hfid.md), [mutations.md](mutations.md)

Jinja2 computed attributes are schema-defined attributes whose values are derived from other attributes or relationships on the same or related nodes. They use Jinja2 templates for rendering.

## Evaluation Paths

There are three distinct paths for evaluating computed attributes, depending on when and where the triggering change occurs.

### 1. Creation — Inline via `_process_macros()`

**When**: A new node is created (`Node.new()` → `_process_fields()` → `_process_macros()`)

All mandatory Jinja2 computed attributes are evaluated synchronously during node creation. The method iterates over `_computed_jinja2_attributes`, renders each template with resolved variables, and sets the attribute value via a generator method (`_generate_attribute_default` or a custom `generate_<name>`).

Optional computed attributes are **not** evaluated inline at creation — they are handled asynchronously via Prefect (path 3).

### 2. Local Update — Inline via `_recompute_local_jinja2()`

**When**: An existing node is updated and the changed fields include dependencies of a computed attribute on the **same node**.

During `Node._update()`, after persisting attribute and relationship changes, `_recompute_local_jinja2()` is called. It:

1. Queries `schema_branch.computed_attributes.get_local_jinja2_targets()` to find self-targeting computed attributes whose dependencies overlap with the changed fields
2. Returns targets in **dependency order** — if computed attribute `fqdn` depends on `label`, and `label` depends on `name`, updating `name` recomputes `label` first, then `fqdn`
3. For each target, renders the Jinja2 template, validates the result, and persists it
4. Tracks failed attributes to prevent cascading from broken computations

This path eliminates background task overhead for local changes and provides immediate results in mutation responses.

### 3. Remote Update — Async via Prefect

**When**: A peer node's attribute changes, affecting a computed attribute on a different node (e.g., changing a device's `role.name` triggers recomputation of the device's `label` which references `{{ role__name__value }}`).

These changes are handled by Prefect background tasks triggered by `NodeCreatedEvent` / attribute change events. The async path uses `ComputedAttrJinja2TriggerDefinition` to match events to affected computed attributes.

## Self-Targeting Filter (`targets_self`)

`ComputedAttrJinja2TriggerDefinition` has a `targets_self` property that returns `True` when `trigger_kind == computed_attribute.kind` — meaning the trigger node kind is the same as the node kind owning the computed attribute.

The async Prefect path **skips** triggers where `targets_self is True`, because those are already handled synchronously by `_recompute_local_jinja2()` during the update mutation. This prevents duplicate computation.

## Extra Filters for Relationship Peers

**Location**: `Node._collect_extra_filters()` in `core/node/__init__.py`

When a computed attribute template references peer attributes (e.g., `{{ role__name__value }}`), those attributes must be loaded during `resolve_relationships()`. The `_collect_extra_filters()` method reads `relationship_fields` from three sources:

```
_collect_extra_filters(schema_branch)
  -> HFID relationship fields       (for new nodes or when HFID is set)
  -> Display label relationship fields (for new nodes or when display_label is set)
  -> Computed attribute relationship fields (for existing nodes / updates)
       via schema_branch.computed_attributes.get_registered_jinja2_node()
```

The computed attribute source is gated by `self._existing` — it only applies during updates, not creation (creation uses `_process_macros()` which resolves its own variables).

## Schema Registration

**Location**: `core/schema/schema_branch_computed/`

The `ComputedAttributes` facade on `SchemaBranch` maintains a registry of Jinja2 computed attributes per node kind. Registration happens during schema processing via `register_computed_jinja2()`.

Each registered node stores:

- **`local_fields`**: Attribute dependencies on the same node (e.g., `{"name", "label"}`)
- **`relationship_fields`**: Map of relationship name → peer attribute names (e.g., `{"role": {"name"}}`)
- **Local dependency graph**: Tracks which computed attributes depend on other computed attributes on the same node, enabling correct evaluation order

Key methods:

| Method | Purpose |
|--------|---------|
| `get_registered_jinja2_node(kind)` | Returns the registered node definition for a kind |
| `get_local_jinja2_targets(kind, updates)` | Returns self-targeting targets whose dependencies overlap with changed fields, in dependency order |

## Lifecycle Summary

| Event | Path | Method | Scope |
|-------|------|--------|-------|
| Node creation (mandatory attrs) | Inline | `_process_macros()` | All mandatory computed attrs |
| Node creation (optional attrs) | Async | Prefect task | Optional computed attrs |
| Local attribute/relationship change | Inline | `_recompute_local_jinja2()` | Self-targeting computed attrs |
| Remote peer attribute change | Async | Prefect task | Cross-node computed attrs |

## Key Files

| File | What |
|------|------|
| `core/node/__init__.py` | `_process_macros()`, `_recompute_local_jinja2()`, `_collect_extra_filters()` |
| `core/schema/schema_branch_computed/facade.py` | `ComputedAttributes` facade, `get_local_jinja2_targets()` |
| `core/schema/schema_branch_computed/jinja2.py` | `RegisteredNodeComputedAttribute`, dependency ordering |
| `computed_attribute/models.py` | `ComputedAttrJinja2TriggerDefinition`, `targets_self` property |
| `computed_attribute/tasks.py` | Prefect task definitions for async recomputation |
| `computed_attribute/gather.py` | Gathers computed attribute triggers from schema |

## See Also

- [Testing](testing.md) — integration_docker test patterns for computed attributes
- [Mutations](mutations.md) — where `_recompute_local_jinja2()` fits in the update flow
- [Display Labels & HFID](display-labels-and-hfid.md) — parallel `_collect_extra_filters()` pattern
