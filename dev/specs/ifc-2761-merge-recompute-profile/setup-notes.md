# T001 Setup notes: pinned reuse points + resolved OPEN items

**Date**: 2026-06-24 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Tasks**: [tasks.md](./tasks.md)

Verified against the current branch tree (`merge-recompute-profile-ifc-2761`) before writing any harness code. Every anchor below was opened and confirmed; line numbers are current as of this date and are pointers, not contracts.

## Reuse points (confirmed current signatures)

### Recorders + DI scope

- `MemoryInfrahubEvent` — `backend/tests/adapters/event.py:11-16`. Attribute `self.events: list[InfrahubEvent]`; `async def send(self, event) -> None` appends and does **not** forward to Prefect or the bus. Pure recorder.
- `WorkflowRecorder` — `backend/tests/adapters/workflow.py:15-50`. Records `submit_calls` / `execute_calls`; `submit_workflow(...) -> WorkflowInfo(id=uuid4())`; does not submit to Prefect. Helpers `get_submit_calls_for` / `get_execute_calls_for`.
- `build_event_service` — `backend/infrahub/workers/dependencies.py:121-124`, **async**, honors no `config.OVERRIDE` (there is no `config.OVERRIDE.event_service`). Override only via the provider scope.
- `build_workflow` — `dependencies.py:132-139`, honors `config.OVERRIDE.workflow`.
- `dependency_provider` is a `fast_depends` `Provider`; fixture at `backend/tests/conftest.py:147-148`. `Provider.scope(builder, factory)` is a context manager.
- **Canonical injection pattern** — `backend/tests/component/proposed_change/conftest.py:115-127` (workflow) and the stacked form at `backend/tests/component/graphql/mutations/test_branch.py:289-294`:
  ```python
  with (
      dependency_provider.scope(build_event_service, lambda: event_recorder),
      dependency_provider.scope(build_workflow, lambda: workflow_recorder),
  ):
      await merge_branch(branch=branch.name, context=context)
  ```
  The lambda signature must match the builder (e.g. `build_database` needs `lambda singleton=True: db`). `_singletons` persists across tests; the scope override takes precedence, but clear singletons if a stale event service was already built.

### Merge / rebase entry points + diff pre-compute

- `merge_branch(branch: str, context: InfrahubContext, proposed_change_id: str | None = None)` — `backend/infrahub/core/branch/tasks.py:278-327`, decorated `@flow`. Resolves the event service via `get_event_service()` (line 325) and emits one node event per changelog (313-327) through `event_service.send(event=...)`.
- `rebase_branch(branch: str, context: InfrahubContext, send_events: bool = True)` — `tasks.py:120-121`; emits per-node events at `:259-275`. Pass `send_events=True`.
- `_do_merge_branch` — `tasks.py:367-508`. Does **not** compute the diff; it **loads** the tracked diff: `diff_repository.get_one(diff_branch_name=branch.name, tracking_id=BranchTrackingId(name=branch.name))` (402-404), then `DiffChangelogCollector(...).collect_changelogs()`.
- `DiffCoordinator.update_branch_diff(base_branch, diff_branch, proposed_change_id=None)` — `backend/infrahub/core/diff/coordinator.py:171-234`. Sets `tracking_id = BranchTrackingId(name=diff_branch.name)` (line 174) and persists the enriched diff under it (195). **This is the key fact**: calling it before `merge_branch` registers exactly the tracking_id `_do_merge_branch` loads.
- Build the coordinator via the component registry (not direct construction):
  ```python
  component_registry = get_component_registry()
  diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
  ```
  Pattern source: `backend/tests/component/core/test_branch_merge.py:39-48` (but note that test drives `diff_merger.merge_graph(at=...)` directly, which does **not** emit node events — it is a model only for building the coordinator and pre-computing the diff, not for the event-emitting path).
- **Do not** model on `backend/tests/component/core/diff/test_merge_task_lock.py` — it patches `infrahub.core.branch.tasks._do_merge_branch` (line 80) and never runs a real merge.
- `NodeMutatedEvent` has no `get_messages()` override; base returns `[]` (`events/node_action.py:16`, `events/models.py:183-184`) — a `BusRecorder` would capture nothing. Event-service recorder is required.

### Timing layer (full stack)

- Recompute deployment names to filter flow runs by (`backend/infrahub/workflows/catalogue.py`):
  - computed attr (Jinja2): `computed-attribute-jinja2-update-value` (per-node value), `trigger_update_jinja2_computed_attributes` (fan-out trigger).
  - display label: `display-label-jinja2-update-value`, `display-label-process-jinja2`, `trigger-update-display-labels`.
  - HFID: `hfid-update-value`, `hfid-process`, `trigger-update-hfid`.
- Flow-run query surface — `backend/infrahub/task_manager/task.py`: `read_flow_runs(flow_filter, flow_run_filter, limit, offset, sort)` and `count_flow_runs(...)`. Accepts `FlowFilterName(any_=workflows)` (filter by deployment/flow name), `FlowRunFilterTags(all_=...)` (**AND-only**), `FlowRunFilterStartTime(before_=...)`, `FlowRunFilterState`. Confirmed at `:226-232`: **only one related node** (`related_nodes[0]`) and AND-only tags — so a seeded-node-id-set filter is impossible.
- Recompute-wait pattern (integration_docker) — `client.task.count(filters=TaskFilter(workflow=[...], related_node__ids=[...], state=terminal))`; `TaskFilter`/`TaskState` from `infrahub_sdk.task.models`; terminal = `COMPLETED/FAILED/CRASHED/CANCELLED`; `PREFECT_EVENT_WAIT_SECONDS = 60` at `backend/tests/helpers/constants.py:20`. Source: `test_display_label_backfill.py:29-55`.
- Bulk seed (full stack) — `client.create_batch()` then `batch.add(task=node.save, node=node, allow_upsert=...)`, execute via `async for _, _ in batch.execute(): pass`. Source: `backend/tests/benchmark/intensive/test_batch_create.py:28-94`.

## Resolved OPEN items

### R5 — derived expected-recompute: **in-process derived**, not Prefect-no-worker

Decision: compute the estimate in-process. Prefect-no-worker is technically possible (the test Prefect server and worker are decoupled — `backend/tests/helpers/utils.py:48-91`, `test_worker.py:88-124`) but costs container startup + setup-flow latency for a number the timing layer already produces authoritatively. In-process is microseconds and deterministic.

Per-family matcher availability (the divergence risk the spec flags):
- Jinja2 computed attr: a public matcher exists — `schema_branch.computed_attributes.get_impacted_jinja2_targets(kind, updates)` (`core/schema/schema_branch_computed/jinja2.py:279-297`), used in production at `computed_attribute/tasks.py:343-347`. Reuse it directly.
- Display label / HFID: **no** clean public per-node matcher; walk the schema trigger structures (`schema_branch.display_labels` template/related-trigger nodes; `hfid` equivalent). This reimplements matching → must be cross-checked against the timing layer's executed count, which stays authoritative.
- Scoping primitives available for reuse: `RecomputeScoper`, `DependencySet`, `ChangedElementSet`, `ComputedAttributeRef`, `IMPRECISE_READ_FIELDS = {"display_label","hfid"}` (`computed_attribute/scoping.py`; `IMPRECISE_READ_FIELDS` defined in `core/schema/schema_branch_computed/python_transform.py:19`). These target the **schema-change** scoping path, not per-node events, so they inform but do not directly implement the per-node estimate.

### R6 — per-merge flow-run timing filter: **flow-name + branch-tag + start-time window on a dedicated branch**

Filter `read_flow_runs` by `FlowFilterName(any_=[recompute deployment names])` + `FlowRunFilterTags(all_=[branch tag])` + `FlowRunFilterStartTime` window. Node-id-set filtering is impossible (single related node, AND-only tags). Run the timed merge on a dedicated branch with no other workflow traffic so the window/branch filter isolates this merge's recompute. This is the riskiest measurement step (T015) — validate before trusting numbers.

## New finding affecting tasks

**Timing-layer gating (T018) needs an explicit skip, not just a timeout.** CI runs `pytest backend/tests/integration_docker/` unconditionally (`.github/workflows/ci.yml:727`, no ignore/skip for that dir). The intensive-benchmark gating (`--ignore=backend/tests/benchmark/intensive` + a CI label) has no equivalent for a single integration_docker file. So `test_merge_recompute_timing.py` must self-gate with an env-gated skip (e.g. `@pytest.mark.skipif(not os.environ.get("INFRAHUB_PROFILE_TIMING"), ...)`) plus the long `@pytest.mark.timeout(...)`, or it will run in normal CI.

## Residual runtime risk — RESOLVED by T006

The component conftest provides an ephemeral Prefect test harness (`prefect_test_harness`, autouse), so calling the real `merge_branch` `@flow` directly works in the counting harness — `add_tags`/`get_run_logger` resolve against the test runtime. Confirmed by a passing run: a data-only merge of 10 changed nodes, driven via `merge_branch(branch=..., context=...)` with `build_database`/`build_event_service`/`build_workflow` scoped to `db`/`MemoryInfrahubEvent`/`WorkflowRecorder`, emits exactly 10 `NodeUpdatedEvent`. The fallback (driving `_do_merge_branch` + replicating the emission loop) is not needed.

Driver preconditions that proved necessary:
- `lock.initialize_lock(local_only=True)` before the merge (the merge takes a global lock).
- `dependency_provider.scope(build_database, lambda singleton=True: db)` so the flow's own `get_database()` session targets the test db.
- `diff_coordinator.update_branch_diff(base_branch=default, diff_branch=branch)` before the merge, to register `BranchTrackingId(name=branch)`.
- Baseline nodes seeded on default **before** `create_branch` (fork ordering), then mutated on the branch.

Requires Neo4j on `localhost:7687` (`neo4j/admin`); `invoke dev.deps` pulls the unbuilt app image, so a standalone `neo4j:2026.05.0-enterprise` container with APOC is the lighter way to run the counting layer locally.

## Key discovery (from running the full-stack timing layer)

The spec's original cost model ("one node event per changed node → one recompute job") is incomplete. Verified empirically on the full stack:

- **Same-node derived values recompute inline.** When a node's own field changes, its computed attribute / display label / human-friendly id are recomputed synchronously as part of the save. This creates **zero** asynchronous recompute work. A direct `name` edit (and a merge of `name` edits) produced no `*-update-value` flow runs at all.
- **The asynchronous recompute fan-out is cross-node.** When a node that other nodes *read* (here, a peer referenced via `peer__name__value`) changes, each reader recomputes asynchronously. Editing one peer read by two nodes produced `+2 computed-attribute-jinja2-update-value` and `+2 display-label-jinja2-update-value`. The human-friendly id reads only the local name, so it does **not** fan out on a peer change.
- **Consequence for the profile:** the merge/rebase recompute cost scales with `(changed nodes that are read by others) × (their readers) × (families that read across the relationship)`, not with the raw changed-node count. The harness therefore profiles a cross-node change (mutating peers the mains read); mutating the mains' own field is kept as a control that shows events-without-fan-out.

Full-stack timing for the cross-node merge (deployment filter + before/after delta on a dedicated branch, default Neo4j community image from the testcontainer stack; each changed peer read by 1 main):

| changed nodes | merge critical path (s) | recompute window (s) | executed recompute runs |
|---------------|-------------------------|----------------------|-------------------------|
| 10            | 20.6                    | 6.2                  | 20 (10 computed + 10 display; no hfid) |
| 100           | 13.6                    | 56.8                 | 200                     |
| 1000          | 27.6                    | 638.9 (~10.6 min)    | 2000                    |

Executed recompute is exactly linear; the recompute window grows linearly and dominates at scale; the merge critical path is fixed overhead. The 1000-node run needs raised budgets (`_wait_idle` cap and the test timeout) because the baseline **creation** of 2000 nodes itself dispatches ~5000 recompute flows (creation fans out, ~3 per all-three-families node) that must drain before the merge is measured.

Run recipe: `INFRAHUB_IMAGE_VER=local-dev INFRAHUB_TESTING_IMAGE_VER=local-dev uv run invoke dev.build` then `INFRAHUB_PROFILE_TIMING=1 INFRAHUB_TESTING_IMAGE_VER=local-dev INFRAHUB_PROFILE_SCALE=<n> uv run pytest backend/tests/integration_docker/test_merge_recompute_timing.py`. The test class overrides `infrahub_version -> "local"`, which the testcontainer harness swaps for `INFRAHUB_TESTING_IMAGE_VER`.
