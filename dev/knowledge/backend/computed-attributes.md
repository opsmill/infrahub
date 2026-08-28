# Computed Attributes

> Part of: `dev/knowledge/backend/` | Related: [display-labels-and-hfid.md](display-labels-and-hfid.md), [mutations.md](mutations.md), [merge-recompute.md](merge-recompute.md)

Computed attributes are schema-defined attributes whose values Infrahub derives instead of a user setting them. There are two kinds: **Jinja2** attributes rendered from a template, and **Python transform** attributes whose value comes from running a Python transformation. The Jinja2 sections come first; Python transform computed attributes have their own section below.

## Jinja2 Evaluation Paths

There are four distinct paths for evaluating computed attributes, depending on when and where the triggering change occurs.

### 1. Creation — Inline via `_process_macros()`

**When**: A new node is created (`Node.new()` → `_process_fields()` → `_process_macros()`)

All self-targeting Jinja2 computed attributes (both mandatory and optional) are evaluated synchronously during node creation. The method iterates over `_computed_jinja2_attributes`, renders each template with resolved variables, and sets the attribute value via a generator method (`_generate_attribute_default` or a custom `generate_<name>`).

Optional **cross-node** computed attributes (those referencing peer relationships) are handled asynchronously via Prefect (path 3), since the async trigger for optional attrs includes `NodeCreatedEvent`.

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

### 4. Merge / Rebase — Coalesced via a bulk recompute

**When**: A branch merge or rebase changes nodes that feed computed attributes.

A merge or rebase runs a single coalesced recompute for the whole change set, writes the results in bulk, and chains any value that reads them. For computed attributes, display labels and human-friendly ids it replaces the per-node path entirely: their triggers are suppressed for merge/rebase/recompute-origin events, so the change is processed once. Python transform computed attributes join the pass when `INFRAHUB_COALESCE_PYTHON_RECOMPUTE_AFTER_MERGE` is on, which is the default, but their per-node automations keep firing, so that family is processed twice until those automations are gated. See [merge-recompute.md](merge-recompute.md).

## Self-Targeting Filter (`targets_self`)

`ComputedAttrJinja2TriggerDefinition` has a `targets_self` property that returns `True` when `trigger_kind == computed_attribute.kind` — meaning the trigger node kind is the same as the node kind owning the computed attribute.

The async Prefect path **neutralizes** self-targeting triggers by replacing their field matchers with placeholder fields that never match real `NodeUpdatedEvent`s, because those are already handled synchronously by `_recompute_local_jinja2()` during the update mutation. The trigger definitions are kept (rather than removed entirely) so they remain available for schema-change detection in the setup flow. This prevents duplicate computation while preserving bulk-recomputation capability.

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

## Jinja2 Lifecycle Summary

| Event | Path | Method | Scope |
|-------|------|--------|-------|
| Node creation (self-targeting attrs) | Inline | `_process_macros()` | All self-targeting computed attrs (mandatory and optional) |
| Node creation (cross-node optional attrs) | Async | Prefect task | Optional cross-node computed attrs (via `NodeCreatedEvent`) |
| Local attribute/relationship change | Inline | `_recompute_local_jinja2()` | Self-targeting computed attrs |
| Remote peer attribute change | Async | Prefect task | Cross-node computed attrs |
| Branch merge or rebase | Coalesced | `CoalescedRecomputeBuilder` + `BulkRecomputeWriter` | Affected computed attrs across the whole change set |

## Python Transform Computed Attributes

Python transform computed attributes take their value from a Python transformation rather than a Jinja2 template. The schema wires an attribute to a transform with `computed_attribute: {kind: TransformPython, transform: <name-or-id>}`. Computation always runs asynchronously in a worker, so the value appears a few seconds after the triggering change.

### Registration

The `ComputedAttributes` facade builds `python_attributes_by_transform`, a `dict[transform -> list[PythonDefinition]]` keyed by the raw `transform` value, which is **either a transform name or a transform UUID**. One transform can feed several attributes; one attribute is fed by exactly one transform.

### Recompute Drivers

Two independent paths recompute these attributes:

- **Schema change** — a `SchemaUpdatedEvent` runs `computed_attribute_setup_python`, which reconciles the automations and, via `RecomputeScoper`, submits a recompute only for the attributes whose backing fields changed.
- **Git change** — importing a repository writes each transform's `fingerprint`. That write emits a `CoreTransformPython` node lifecycle event, matched by three builtin triggers:

| Trigger | Event | Match | Action |
|---------|-------|-------|--------|
| created | `NodeCreatedEvent` | kind + `origin=live` | recompute the attributes it feeds (first computation) |
| updated | `NodeUpdatedEvent` | kind + `origin=live` + related `field.name == fingerprint` | selective recompute |
| deleted | `NodeDeletedEvent` | kind + `origin=live` | reconcile automations (prunes the removed transform's) |

All three run `process_transform_lifecycle`. On create or update it waits for the schema to converge, then `TransformRecomputeSubmitter` resolves the transform to its attributes through `RecomputeResolver` and fans out one recompute per attribute across every node of each attribute's kind. Every event, including a delete or a failed recompute, reconciles the node-input automations in a `finally` block.

`RecomputeResolver` looks the transform up by **both** name and UUID and dedupes by `(kind, attribute)`, so an attribute wired by name and another wired by UUID both recompute for the same transform.

### Node-Input Automations

Besides the transform-lifecycle triggers, each `(kind, attribute)` has a data-path automation that recomputes the value when a node feeding the transform's query changes. `_reconcile_python_computed_attribute_automations` rebuilds these from the schema. One gather builds both trigger lists and they are applied under a single trigger-registry lock, so a concurrent reconcile cannot delete an automation another run just created, and a transform delete prunes its automation rather than leaving it stale.

### Batch Execution

`process_transform` processes its node ids as one batch per attribute, not one task per node:

- It recomputes the one attribute named in `computed_attribute_name`. Every caller submits one flow per attribute, so processing every Python attribute of the kind would run each transform once per attribute of that kind.
- The transform's git repository is initialized once for the whole batch and shared across the per-node executions. Transform execution must not mutate the shared checkout.
- Each node's read still runs individually with `update_group=True`, keeping the node subscribed to the transform's query group (the reverse index that routes future source changes to affected readers).
- A coalesced pass tells the flow so through `coalesced` and `recompute_depth`: its writes are stamped with the recompute origin and drive the next chain level, instead of re-entering the live per-node paths with no depth guard.
- The recomputed values persist through the shared bulk recompute writer (bounded transactions), not via per-node GraphQL mutations. The writer's skip-unchanged gating is per node, not per value: a save that produces no effective change emits no event and dispatches no follow-on recompute, which is what keeps a wide fan-out from echoing into further waves. A node whose save changes another of its fields still emits an event.
- A node whose transform raises or returns a non-string is skipped with its previous value intact and a logged reason; the rest of the batch persists. The flow ends with a `submitted/written/skipped` summary line.
- Each submission carries the branch tag at creation so the flow run stays visible in branch-filtered task queries; tags added mid-run do not survive later in-flow tag updates.
- Crash semantics: the writer commits in bounded chunks, so a mid-batch crash leaves earlier chunks persisted. Recovery is re-running the recompute; skip-unchanged makes redone work no-op-cheap. Rollback of the whole feature is a clean revert (no schema or data migration).

### Invariants

- **Over-recompute is acceptable, under-recompute is not.** Any fallback or error path recomputes rather than risk a stale value.
- **The `origin=live` filter** keeps merge and rebase replays out; those are handled by the coalesced merge/rebase recompute path, so the lifecycle triggers do not fire a second time.
- **The recompute write targets the attribute's own node kind, not `CoreTransformPython`,** so it never re-fires the lifecycle triggers (no loop).
- **A null fingerprint** (a pre-upgrade node) is treated as unknown: the first import stamps a value and recomputes once, then self-heals.
- **No `watch` declaration** folds the commit id into the fingerprint, so such a transform recomputes on every commit, but still only its own attributes.

## Key Files

| File | What |
|------|------|
| `core/node/__init__.py` | `_process_macros()`, `_recompute_local_jinja2()`, `_collect_extra_filters()` |
| `core/schema/schema_branch_computed/facade.py` | `ComputedAttributes` facade, `get_local_jinja2_targets()`, `python_attributes_by_transform` |
| `core/schema/schema_branch_computed/jinja2.py` | `RegisteredNodeComputedAttribute`, dependency ordering |
| `computed_attribute/models.py` | `ComputedAttrJinja2TriggerDefinition`, `targets_self` property |
| `computed_attribute/tasks.py` | Prefect flows: async recomputation, `process_transform_lifecycle`, automation reconcile |
| `computed_attribute/gather.py` | Gathers computed attribute triggers from schema |
| `computed_attribute/triggers.py` | `CoreTransformPython` lifecycle triggers (create/update/delete) |
| `computed_attribute/recompute_resolution.py` | `RecomputeResolver` — transform to the attributes it feeds |
| `computed_attribute/transform_recompute.py` | `TransformRecomputeSubmitter` — per-attribute recompute fan-out |

## See Also

- [Testing](testing.md) — integration_docker test patterns for computed attributes
- [Mutations](mutations.md) — where `_recompute_local_jinja2()` fits in the update flow
- [Display Labels & HFID](display-labels-and-hfid.md) — parallel `_collect_extra_filters()` pattern
- [Merge/Rebase Recompute](merge-recompute.md) — the coalesced recompute path for merges and rebases
