# Follow-up: extract `core/regeneration` package

**Jira**: IFC-2908 · **Parent feature**: IFC-2704 incremental merge regeneration · **Status**: planned (not in the US1 increment)

Deferred refactor agreed during IFC-2704. Not part of the US1 increment; tracked separately.

## Problem

The merge selective-regeneration path reuses the proposed-change selection primitives. Those
primitives live in `backend/infrahub/proposed_change/tasks.py`, which imports `merge_branch` from
`backend/infrahub/core/branch/tasks.py`. The merge selection code is the
`backend/infrahub/core/merge/selective_regen/` package; several of its modules import the primitives
from `proposed_change/tasks.py`, so wiring the merge dispatcher into `branch/tasks.py` closes a
cycle:

```text
branch/tasks.py -> (lazy) merge/selective_regen/orchestrator.py
                -> merge/selective_regen/{gate,impacted,definition_selector/*}.py
                -> proposed_change/tasks.py -> branch/tasks.py (merge_branch)
```

`regeneration_dispatcher.py` sits between `branch/tasks.py` and the orchestrator but imports it only
under `TYPE_CHECKING`; the runtime edge is the function-local import in
`_build_post_merge_regeneration_dispatcher`.

Two consequences:

1. `_build_post_merge_regeneration_dispatcher` in `branch/tasks.py` uses function-local (lazy)
   imports (`regeneration_dispatcher`, `selective_regen.orchestrator`) to avoid the cycle.
2. The `core/merge/selective_regen/` package reaches into underscored internals of
   `proposed_change/tasks.py` (code-review finding #5), coupling the two modules.

A secondary concern: the merge follow-up runs in the task worker with direct database access, yet
the reused primitives go through the SDK HTTP client. The artifact gather in
`definition_selector/artifact_selector.py` uses a raw GraphQL string (`GATHER_ARTIFACT_DEFINITIONS`,
a fork of the one in `proposed_change/tasks.py` with the extra `targets`/`parameters` fields the
merge path needs) because an artifact definition needs a two-level relationship traversal
(`definition -> transformation -> query`/`repository`) that one-level
`client.filters(prefetch_relationships=True)` cannot fetch in a single round trip.

## Current state

### Merge package layout (`core/merge/selective_regen/`)

| Module | Contents | Imports from `proposed_change` |
|---|---|---|
| `orchestrator.py` | `MergeSelectiveRegeneration`, `RegenerationSelector` (Protocol), `build_merge_selective_regeneration` | `get_modified_kinds` (from `proposed_change.branch_diff`) |
| `gate.py` | `DefinitionGate` | `DefinitionSelect`, `_definition_changed`, `_query_changed` |
| `impacted.py` | `ImpactedSubscriberResolver` | `ImpactScope`, `get_field_level_impacted_subscribers`, `ImpactedSubscribers` |
| `models.py` | `LoadedDefinition`, `SelectiveRegenerationPlan`, `GateResult` (merge-specific) | — |
| `definition_selector/base.py` | `DefinitionSelectorBase`, `_fetch_member_ids` | `_map_subscriber_ids_by_member` |
| `definition_selector/artifact_selector.py` | `ArtifactSelector`, forked `GATHER_ARTIFACT_DEFINITIONS` | `_parse_artifact_definitions`, `_should_render_artifact` |
| `definition_selector/generator_selector.py` | `GeneratorSelector` | `_run_generator` |

### Extraction target

| Item | Detail |
|---|---|
| Cycle edges | `proposed_change/tasks.py` imports `merge_branch`; the `selective_regen/` package modules import the primitives |
| Shared cluster | `DefinitionSelect`, `ImpactScope`, `ImpactedSubscribers`, `PredicateOutcome`, `RegenerationDefinition`, `_query_changed`, `_definition_changed`, `_relevant_node_changes`, `_is_triggering_action`, `_TRIGGERING_DIFF_ACTIONS`, `_should_render_artifact`, `_run_generator`, `_map_subscriber_ids_by_member`, `_parse_artifact_definitions`, `get_field_level_impacted_subscribers`, `_get_subscribers_for_nodes`, `GATHER_GRAPHQL_QUERY_SUBSCRIBERS`, `GATHER_ARTIFACT_DEFINITIONS` |
| Already external | `ProposedChangeSubscriber` (`message_bus/types.py`) and `get_modified_kinds` (`proposed_change/branch_diff.py`) are already outside `tasks.py`; leave them where they are |
| Pure (no client/DB) | Everything in the shared cluster except the two rows below |
| Client/DB-bound | `get_field_level_impacted_subscribers` (uses `get_database()` + the GraphQL analyzer) and `_get_subscribers_for_nodes` (one `client.execute_graphql`) |
| Consumers | `proposed_change/tasks.py` (`run_generators`, `refresh_artifacts`, `validate_artifacts_generation`, `request_generator_definition_check`) and the `core/merge/selective_regen/` package |

## Target shape

New leaf package `backend/infrahub/core/regeneration/` that imports neither `branch.tasks` nor
`proposed_change.tasks`. This is orthogonal to the existing `core/merge/selective_regen/` package:
that package stays as the merge-side orchestration and only re-points its imports at the new leaf.

```text
core/regeneration/
- models.py        # RegenerationDefinition, PredicateOutcome, DefinitionSelect, ImpactScope, ImpactedSubscribers
- predicates.py    # query_changed, definition_changed, relevant_node_changes, triggering-action helpers
- members.py       # map_subscriber_ids_by_member, should_render_artifact, run_generator
- definitions.py   # parse_artifact_definitions + the single shared GATHER_ARTIFACT_DEFINITIONS
- impact.py        # get_field_level_impacted_subscribers, get_subscribers_for_nodes, subscriber query
```

Names that cross the package boundary become public (drop the leading underscore).

## Phase 1: pure move — done

Achieves the cycle break and the decoupling. Behaviour-neutral. Delivered on
`pmi-20260717-refactoring-pc-merge-selective`, extended to fold in the B1/B2 predicate candidates
(`transform_changed`, `repo_diff_or_none`) so the predicate family lives whole in `predicates.py`.
The package layout landed as planned; boundary-crossing names dropped their leading underscore. No
live fork of `GATHER_ARTIFACT_DEFINITIONS` remained in `artifact_selector.py` (already reconciled to
the shared gather), so step 3 was a straight re-point.

1. Create `core/regeneration/` and move the cluster verbatim, keeping the existing SDK-client
   signatures on `get_field_level_impacted_subscribers` and `_get_subscribers_for_nodes`.
2. `proposed_change/tasks.py`: remove the moved definitions, import them from `core.regeneration`.
   Callers keep passing `client` and the resolved `diff_summary` unchanged.
3. `core/merge/selective_regen/`: re-point the package's imports (`gate.py`, `impacted.py`,
   `definition_selector/base.py`, `definition_selector/artifact_selector.py`,
   `definition_selector/generator_selector.py`) at `core.regeneration`; use the single shared
   `definitions.GATHER_ARTIFACT_DEFINITIONS` and delete the fork in `artifact_selector.py`. The
   `targets`/`parameters` fields the merge path needs become part of the shared gather (unused by
   the proposed-change caller).
4. `core/branch/tasks.py`: promote the lazy imports in `_build_post_merge_regeneration_dispatcher`
   (`regeneration_dispatcher`, `selective_regen.orchestrator`) to top-level; remove the lazy-import
   note.
5. Confirm the cycle is gone (import `branch.tasks` with no lazy shim; assert nothing in
   `core/regeneration` imports `branch.tasks` or `proposed_change.tasks`).

**Risk**: low (relocation). **Verification**: full `proposed_change` unit suite, the merge unit
suite, the selective-regeneration integration test, `ruff`, `ty`, and an import-cycle check.
**Blast radius**: import lines in `proposed_change/tasks.py`, the new package, the
`selective_regen/` package modules, and `branch/tasks.py`. No logic changes.

## Phase 2: DB-direct (optional, separately shippable)

Justified only by a measured round-trip or performance concern. Touches only the client-bound
edges; the pure primitives from Phase 1 are untouched.

| Today (SDK client) | DB-direct replacement | Location today |
|---|---|---|
| `client.execute_graphql(GATHER_ARTIFACT_DEFINITIONS)` | `NodeManager.query(CoreArtifactDefinition, ...)` resolving `transformation -> query`/`repository` | `definition_selector/artifact_selector.py` (→ `core/regeneration/definitions.py` after Phase 1) |
| `client.filters(GENERATORDEFINITION / GENERATORINSTANCE / ARTIFACT)` | `NodeManager.query(...)` with the same filters | `definition_selector/generator_selector.py`, `definition_selector/artifact_selector.py` |
| `fetch_*_targets(client, ...)` -> `client.get(CoreGroup, include=members)` | `NodeManager.get_one` + relationship resolve on `db` | `_fetch_member_ids` in `definition_selector/*.py`; helpers in `git/utils.py` (move to `core/regeneration/targets.py`) |
| `_get_subscribers_for_nodes` -> `client.execute_graphql(GATHER_GRAPHQL_QUERY_SUBSCRIBERS)` | `NodeManager` query over `CoreGraphQLQueryGroup.subscribers` | `impact.py` |
| `prepare_graphql_params(db=await get_database())` | already DB-based; keep | `impact.py` |

Design change: the components take `db: InfrahubDatabase` and `branch` (constructor-injected)
instead of a `client`. `MergeSelectiveRegeneration` receives `db`/`branch` (already in scope in the
follow-up flow) rather than `get_client()`. The artifact gather becomes a typed `NodeManager` query
with no raw GraphQL string.

Constraint: `get_field_level_impacted_subscribers` and its helpers are shared, so converting them
to DB-direct changes the proposed-change callers too. Preferred approach: define a small
`SubscriberResolver` / `DefinitionSource` protocol with two implementations (a client-based one for
the proposed-change pipeline, a DB-based one for the merge follow-up), selected at the wiring layer.
This keeps the PC pipeline on its client while the merge path goes DB-direct, and follows the
"interface for two implementations" rule.

**Risk**: medium to high (touches the proposed-change pipeline data access). **Verification**: the
full proposed-change component and integration suites, the merge integration test, the merge
recompute-coalescing suite, and a before/after `NodeManager` query count confirming the round-trip
reduction.

## Sequencing and boundaries

- Phase 1 is behaviour-neutral and unblocks removing the lazy import; run it on its own branch.
- Phase 2 is a separate decision, gated on a measured perf concern; default to the two-implementation
  protocol so the proposed-change path keeps its client.
- Do not fold either phase into the IFC-2704 US1 increment.
- Do not move `merge_branch` or touch the `proposed_change -> branch.tasks` edge; Phase 1 breaks the
  cycle from the `selective_regen` side, which is cleaner.
