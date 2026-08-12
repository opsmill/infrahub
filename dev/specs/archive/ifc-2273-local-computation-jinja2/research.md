# Research: Local Computation of Jinja2 Computed Attributes

## R1: Where to hook inline recomputation in the update path

**Decision**: Add a `_recompute_local_jinja2()` method to `Node` and call it from `_update()`, after attribute and relationship saves but before HFID/display_label recomputation.

**Rationale**: The `_update()` method in `core/node/__init__.py:901` already follows this pattern for HFID and display_label — it checks `needs_update(fields)`, calls `compute()`, then `save()`. Jinja2 computed attributes should follow the same pattern. Placing it before HFID/display_label ensures computed attributes are persisted before HFID/display_label recomputation (in case HFID/display_label depends on a computed attribute).

**Alternatives considered**:
- Hook at `Node.save()` level: Too high — `save()` delegates to `_create()` or `_update()` and we only want the update path.
- Hook at `mutate_update()` level in `graphql/mutations/main.py`: Too high — would not cover SDK mutations or non-GraphQL update paths.
- Separate post-save step: Requires an extra DB transaction; the existing in-`_update()` pattern is simpler and atomic.

## R2: How to identify locally-affected computed attributes

**Decision**: Use the existing `ComputedAttributes.get_impacted_jinja2_targets(kind, updates)` method with `updates` set to the list of changed fields, then filter for targets where `target.kind == self._schema.kind` (i.e., the computed attribute is on the same node being updated).

**Rationale**: The registry already tracks which fields trigger which computed attributes. The `kind` field on `ComputedAttributeTarget` identifies where the computed attribute lives. When `target.kind == self._schema.kind`, the trigger and the computed attribute are on the same node — a local change. The registry stores entries for the node's own kind with local attribute names and relationship names as keys (see `register_computed_jinja2` lines 156-168).

**Alternatives considered**:
- Parsing the Jinja2 template on every update: Expensive and redundant — the registry already pre-computes dependencies.
- Adding a new `targets_self` filter to `get_impacted_jinja2_targets()`: Cleaner but adds complexity to a method also used by the Prefect path. Simple post-filter is sufficient.

## R3: How to render the Jinja2 template inline during updates

**Decision**: Extract the template rendering logic from `_process_macros()` into a reusable helper, or directly reuse `_process_macros()` with a parameter to indicate which attributes to recompute (instead of using `self._computed_jinja2_attributes` which is only populated during creation).

**Rationale**: `_process_macros()` (lines 645-719 of `core/node/__init__.py`) already handles:
1. Getting the Jinja2 template from `attr_schema.computed_attribute.jinja2_template`
2. Parsing variables via `InfrahubJinja2Template.get_variables()`
3. Resolving local attributes from `self` and relationship peers via `get_peer()` + `get_one_by_id_or_default_filter()`
4. Rendering via `jinja_template.render(variables=...)`

For the update path, the node already has loaded attributes and resolved relationships (after `resolve_relationships()`). The variables can be resolved from the in-memory node state without extra DB queries (for local attributes) or from the already-resolved relationship peers (for relationship attributes, loaded via the extended `_collect_extra_filters()`).

**Alternatives considered**:
- Calling the same GraphQL-based approach used by `process_jinja2()` in the Prefect path: Overkill — that path issues a GraphQL query because it doesn't have the node in memory. During `_update()`, we already have the node.
- Creating an entirely separate rendering path: Violates DRY. Better to reuse the existing template resolution logic.

## R4: How to load peer attributes needed for relationship-referencing templates

**Decision**: Extend `_collect_extra_filters()` to include computed attribute relationship fields from the `ComputedAttributes` registry, following the same pattern used for display labels and HFIDs.

**Rationale**: `_collect_extra_filters()` already reads `relationship_fields` from `schema_branch.display_labels` and `schema_branch.hfids` registries and passes them to `RelationshipManager.resolve()` as `extra_filters`. The computed attributes registry (`schema_branch.computed_attributes`) needs a similar `relationship_fields` accessor that maps relationship names to the set of peer attribute names needed for template rendering.

The `RegisteredNodeComputedAttribute.relationships` dict already maps relationship names to `ComputedAttributeTarget` lists. We need to also store which specific peer attributes are needed (currently only stored implicitly in the Jinja2 template). This can be extracted during `register_computed_jinja2()` by reading `schema_path.active_attribute_schema.name` for relationship-type paths.

**Implementation detail**: Add a `relationship_fields` property to `RegisteredNodeComputedAttribute` (or a new registry class similar to `TemplateLabel`) that returns `dict[str, set[str]]` mapping relationship names to peer attribute names. Then in `_collect_extra_filters()`, merge these with the existing display_label/HFID extra_filters.

**Alternatives considered**:
- Fetching peers separately after `resolve_relationships()`: Extra DB queries per peer, defeats the purpose.
- Assuming all peer attributes are always loaded: Not true — `resolve()` only loads fields explicitly requested.

## R5: How to suppress background tasks for local changes

**Decision**: Modify the Prefect automation trigger creation in `ComputedAttrJinja2TriggerDefinition.from_computed_attribute()` to skip trigger nodes where `targets_self=True`. This means the automation only fires for remote changes (peer node updates), not for changes to the node's own attributes/relationships.

**Rationale**: The trigger system in `computed_attribute/models.py` creates separate Prefect automations per `ComputedAttributeTriggerNode`. Each trigger node has a `targets_self` flag that is `True` when the trigger node kind matches the computed attribute's node kind (i.e., a local change). By skipping these triggers, the Prefect automation will never fire for local changes — which is correct because they're handled inline.

For computed attributes with mixed local+remote dependencies (e.g., `{{ instance__value }}-{{ site__name__value }}`), the trigger for the own node kind (`TestingDevice`) is skipped (handled inline), while the trigger for the peer kind (`BuiltinLocation`) is preserved (remote changes still go through background tasks).

**Alternatives considered**:
- Adding a `locally_recomputed` field to the event payload: More complex; requires both the event emitter and the Prefect trigger to coordinate.
- Filtering at the Prefect flow level (skip if `node_kind == computed_attribute_kind` and `targets_self`): Wastes Prefect resources creating a flow run just to skip it.
- No suppression — let both inline and background paths run: Would cause double computation and potential race conditions.

## R6: How to handle chained computed attribute dependencies

**Decision**: When multiple computed attributes on the same node need recomputation, sort them by dependency order using a topological sort on the template variable references. If computed attribute A references computed attribute B's value, B must be computed first.

**Rationale**: The spec requires FR-007 (resolve dependency order). In practice, this is rare — most Jinja2 templates reference regular attributes and relationships, not other computed attributes. But it must be handled correctly.

**Implementation**: After identifying affected computed attributes via `get_impacted_jinja2_targets()`, parse each attribute's template variables. If any variable references another computed attribute in the set, compute that one first. A simple iterative approach works (the set is small, typically 1-3 attributes): iterate until all are resolved, computing any attribute whose dependencies are already resolved.

**Alternatives considered**:
- Ignoring the problem: Spec explicitly requires FR-007.
- Pre-computing dependency order at schema registration time: More efficient but adds complexity to the registry. Runtime sorting is simpler given the small set size.

## R7: Event consolidation

**Decision**: No changes needed. The existing event emission in `generate_node_mutation_events()` already emits a single `NodeUpdatedEvent` per mutation. Since inline-computed attribute updates happen within `_update()` and are recorded in the same `NodeChangelog`, they will be included in the same event automatically.

**Rationale**: The `_update()` method builds a single `NodeChangelog` that accumulates all attribute and relationship changes. Adding computed attribute saves to this changelog means they appear as additional `updated_fields` in the event. The event is emitted once after `Node.save()` completes.

**Alternatives considered**: None needed — the existing mechanism handles consolidation by design.
