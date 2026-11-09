# Quickstart: Local Computation of Jinja2 Computed Attributes

## What changes

After this feature, Jinja2 computed attributes on a node are recalculated **immediately** when you update an attribute or relationship on that same node. Previously, all recomputation went through background Prefect tasks.

## User impact

- **No behavioral change**: Computed attributes work the same way. Users see results faster.
- **Mutation responses**: Now include the updated computed attribute values immediately (no page refresh needed).
- **Webhooks**: One event per mutation instead of potentially two (one for the change, one for the computed attribute update).
- **Bulk updates**: No longer spawn thousands of background tasks for local computed attribute changes.

## Developer impact

### _update() now handles computed attributes

The `Node._update()` method in `core/node/__init__.py` now includes a computed attribute recomputation step, following the same pattern as HFID and display_label recomputation:

```python
# In _update(), after attribute/relationship saves:
# 1. Identify locally-affected Jinja2 computed attributes
# 2. Render templates using current node state
# 3. Save updated computed attribute values
# 4. Record in NodeChangelog (same event)
```

### _collect_extra_filters() is extended

The `_collect_extra_filters()` method now also includes relationship fields needed by Jinja2 computed attribute templates, ensuring peer attributes are loaded during `resolve_relationships()`.

### Prefect triggers skip local changes

`ComputedAttrJinja2TriggerDefinition.from_computed_attribute()` no longer creates Prefect automations for trigger nodes where `targets_self=True`. Only remote triggers (peer node changes) go through background tasks.

## Testing

Run the existing computed attribute test suite plus new tests:

```bash
# Unit tests for local target detection
uv run invoke backend.test-unit -- -k test_schema_branch_computed

# Functional tests for inline recomputation
uv run invoke backend.test-unit -- -k test_local_computation
```
