# Reuse points (pinned for implementation)

**Date**: 2026-06-26 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Exact APIs the coalescing work reuses, verified on the rebased branch (current develop). Anchors are file:line at pin time; treat the names as the contract, re-grep if lines drift. The coalesced pass is the data-change path (which reader nodes to recompute), not the schema-change path (`RecomputeScoper`, which selects which definitions to recompute and then recomputes all nodes of a kind).

## 1. Computed attributes (Jinja2) — reuse the data-change deriver, do not rebuild

- `schema_branch.computed_attributes.get_impacted_jinja2_targets(kind, updates) -> list[ResolvedComputedTarget]` (`core/schema/schema_branch_computed/facade.py:66` → `jinja2.py:279`). Given a changed `(kind, fields)` it returns the impacted targets, with the target kind possibly different from the input kind when the dependency crosses a relationship.
- `ResolvedComputedTarget(target=ComputedAttributeTarget(kind, attribute), node_filters: list[str])` (`jinja2.py:34`, `:16`). `node_filters` is `["ids"]` for a self target (the changed node is the target) and `["<rel>__ids"]` for a cross-node target; a self-referential relationship can carry both (`jinja2.py:100-141`).
- Self vs cross discriminator for the coalesced async set: a pure `["ids"]` target is the same-node value (recomputed inline on save, carried over by the merge — research R3/R5), so it is excluded for updates and included for creations; a target with a `<rel>__ids` filter is the cross-node work the coalesced pass owns.

## 2. Display labels — build the deriver here, from this metadata

- Facade `schema_branch.display_labels` (`core/schema/schema_branch_display.py`):
  - `targets_node(kind) -> bool` (`:107`), `get_template_nodes() -> dict[kind, TemplateLabel]` (`:115`) — the self/creation targets.
  - `get_related_trigger_nodes() -> dict[related_kind, RelationshipTriggers]` (`:119`) — the cross-node map: `RelationshipTriggers.attributes: {changed_attr: set[RelationshipIdentifier(kind=target_kind, filter_key="<rel>__ids", template)]}` (`:43-45`, `:33-41`).
  - `get_related_template(related_kind, target_kind) -> TemplateLabel` (`:123`) — resolves the reader `filter_key`.
- Existing data-change mapping logic to mirror (turns a changed `(kind, field)` into per-target-kind readers): `DisplayLabelTriggerDefinition.from_related_node` (`display_labels/models.py:77-109`) and the runtime flow `process_display_label` (`display_labels/tasks.py:85-133`).

## 3. Human-friendly ids — build the deriver here, from this metadata

- Facade `schema_branch.hfids` (`core/schema/schema_branch_hfid.py`): `targets_node` (`:93`), `get_node_definition(kind) -> HFIDDefinition` (`:97`), `get_template_nodes()` (`:101`), `get_related_trigger_nodes()` (`:105`). Same shape as display labels.
- Per-family difference is encoded by the metadata: a self-only HFID (reads only the local name) registers no relationship, so it has no entry in `get_related_trigger_nodes()` and does not fan out on a cross-node update; it still recomputes on creation via the self/`get_template_nodes()` path. No special-casing needed beyond reading the same maps.

## 4. Finding reader nodes — one union query, not one per changed node

- Each family locates readers with a GraphQL `@filters: {filter_key: id}` query: `DisplayLabelJinja2GraphQL.render_graphql_query(filter_id)` (`display_labels/models.py:174-188`), invoked in `process_display_label` (`display_labels/tasks.py:114-116`). HFID and computed mirror this.
- Coalescing (T008): run one query per `(family, target_kind, filter_key)` with `filter_key` set to the union of changed node ids, replacing the per-changed-node queries (Constitution V, no N+1). `__ids` filters accept a list.

## 5. Per-family execution and batching (reuse for submission)

- Process and update flows: `process_display_label` / `display_label_jinja2_update_value` (`display_labels/tasks.py:85`, `:46`); `process_hfid` / update (`hfid/tasks.py`); `process_jinja2` / update (`computed_attribute/tasks.py`).
- Batching: `client.create_batch()` then `batch.add(task=...)` per reader (`display_labels/tasks.py:122-133`). The full-branch Jinja2 loop is the one place without chunking (R4/R8, T018).

## 6. Change set at the emission points

- Merge: `PostMergeDispatcher.dispatch_events` (`core/merge/post_merge.py:106-124`) emits one node event per changed node, built from `DiffChangelogCollector(diff=branch_diff, ...)` in `orchestrator.py:92-98`, on the destination branch. Build/submit the coalesced recompute here instead of relying on those events for the three families.
- Rebase: inline in `rebase_branch` (`core/branch/tasks.py:252-275`), on the user branch.
- Changelog node shape: `(DiffAction, NodeChangelog)` with `node_id` / `node_kind` / changed field names — the input to `MergeChange`.

## 7. No-double-processing precedent (T009)

- `TRIGGER_PLACEHOLDER_FIELD` (`trigger/constants.py:2`) is a field no real event carries; `targets_self` triggers use it so they never match a `NodeMutatedEvent` (`computed_attribute/gather.py:125-131`, `display_labels/models.py:50-62`, `hfid/models.py:50-62`). This is the same-node "free" mechanism, not a merge filter.
- The cross-node (`targets_self=False`) triggers of the three coalesced families are the ones that must stop matching merge/rebase-origin events. T009 stamps a merge/rebase-origin label at the two build sites and adds a negative match to those three families' trigger builders only (`computed_attribute/models.py`, `display_labels/models.py:111-160`, `hfid/models.py`), leaving Python-transform, profiles, action rules, and webhooks untouched.
