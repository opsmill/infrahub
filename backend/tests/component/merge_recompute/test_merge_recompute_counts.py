"""Counting layer for the merge/rebase recompute profile.

Drives a real, data-only merge or rebase over a seeded branch with the event
service and workflow recorders injected through the dependency-provider scope,
then counts the node events emitted and derives the cross-node recompute fan-out.
No task worker runs, so recompute is never dispatched; the timing layer is the
authority on executed recompute.

Two cases are profiled:

- same-node: a node's own ``name`` changes. The merge emits one node event per
  changed node, but the node's derived values recompute inline on save, so there
  is no asynchronous fan-out.
- cross-node: a peer that the mains read changes. The merge still emits one node
  event per changed peer, and each reader recomputes asynchronously: this is the
  fan-out the merge path pays for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch.tasks import merge_branch, rebase_branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.manager import NodeManager
from infrahub.dependencies.registry import get_component_registry
from infrahub.events.node_action import NodeCreatedEvent, NodeDeletedEvent, NodeMutatedEvent, NodeUpdatedEvent
from infrahub.workers.dependencies import build_cache, build_database, build_event_service, build_workflow
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.merge_recompute.dataset import load_profile_schema, seed_branch
from tests.helpers.merge_recompute.estimate import COMPUTED_ATTRIBUTE, DISPLAY_LABEL, HFID, derive_expected_recompute
from tests.helpers.merge_recompute.metrics import RecomputeCounts, classify_growth
from tests.helpers.merge_recompute.scales import CI_SCALES

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

_EVENT_TYPE_BY_CLASS = {
    NodeCreatedEvent: "created",
    NodeUpdatedEvent: "updated",
    NodeDeletedEvent: "deleted",
}


def _count_node_events(events: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if isinstance(event, NodeMutatedEvent):
            label = _EVENT_TYPE_BY_CLASS[type(event)]
            counts[label] = counts.get(label, 0) + 1
    return counts


async def _drive_counts(
    *,
    db: InfrahubDatabase,
    default_branch: Branch,
    dependency_provider: Provider,
    changed_nodes: int,
    branch_name: str,
    operation: str = "merge",
    mutate_kind: str = "peer",
) -> tuple[RecomputeCounts, list[str]]:
    # Merge profiles branch edits (merged into default); rebase profiles default's
    # intervening edits (replayed into the branch).
    mutate_target = "branch" if operation == "merge" else "default"
    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name=branch_name,
        changed_nodes=changed_nodes,
        mutate_target=mutate_target,
        mutate_kind=mutate_kind,
    )

    if operation == "merge":
        # Production precondition for the merge flow: the enriched diff must be
        # tracked under BranchTrackingId(name=branch) before the merge loads it.
        # Rebase computes its own diff, so it needs no pre-step.
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=seeded.branch)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=seeded.branch)

    event_recorder = MemoryInfrahubEvent()
    workflow_recorder = WorkflowRecorder()
    # Develop's merge/rebase path reads a Redis-backed write blocker; inject the
    # in-memory cache adapter so the counting layer needs no external Redis.
    cache = MemoryCache()
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )

    with (
        dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
        dependency_provider.scope(build_event_service, lambda: event_recorder),
        dependency_provider.scope(build_workflow, lambda: workflow_recorder),
        dependency_provider.scope(build_cache, lambda: cache),
    ):
        if operation == "merge":
            await merge_branch(branch=seeded.branch_name, context=context)
        else:
            await rebase_branch(branch=seeded.branch_name, context=context, send_events=True)

    schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
    counts = RecomputeCounts.build(
        changed_nodes=changed_nodes,
        node_events=_count_node_events(event_recorder.events),
        expected_recompute=derive_expected_recompute(schema_branch=schema_branch, events=event_recorder.events),
    )
    return counts, seeded.changed_node_ids


async def test_merge_same_node_change_emits_events_without_fanout(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    counts, _ = await _drive_counts(
        db=db,
        default_branch=default_branch,
        dependency_provider=dependency_provider,
        changed_nodes=10,
        branch_name="profile_same_node",
        mutate_kind="main",
    )

    # One node event per changed node, but the change is same-node, so derived
    # values recompute inline on save and no asynchronous recompute fans out.
    assert counts.node_events == {"updated": 10}
    assert counts.expected_recompute == {COMPUTED_ATTRIBUTE: 0, DISPLAY_LABEL: 0, HFID: 0}


async def test_merge_cross_node_change_fans_out(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    counts, _ = await _drive_counts(
        db=db,
        default_branch=default_branch,
        dependency_provider=dependency_provider,
        changed_nodes=10,
        branch_name="profile_cross_node",
        mutate_kind="peer",
    )

    # One node event per changed peer; each reader's computed attribute and display
    # label fan out. The human-friendly id reads only the local name, so it does not.
    assert counts.node_events == {"updated": 10}
    assert counts.expected_recompute == {COMPUTED_ATTRIBUTE: 10, DISPLAY_LABEL: 10, HFID: 0}


async def test_merge_fanout_growth_across_scales(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    per_scale: dict[str, RecomputeCounts] = {}
    for scale in CI_SCALES:
        counts, _ = await _drive_counts(
            db=db,
            default_branch=default_branch,
            dependency_provider=dependency_provider,
            changed_nodes=scale.changed_nodes,
            branch_name=f"profile_{scale.name}",
            mutate_kind="peer",
        )
        per_scale[scale.name] = counts
        assert counts.node_events == {"updated": scale.changed_nodes}
        assert counts.total_expected_recompute == 2 * scale.changed_nodes

    event_points = [(c.changed_nodes, float(c.total_node_events)) for c in per_scale.values()]
    fanout_points = [(c.changed_nodes, float(c.total_expected_recompute)) for c in per_scale.values()]
    assert classify_growth(event_points) == "linear"
    assert classify_growth(fanout_points) == "linear"


async def test_merge_counts_are_deterministic(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    first, _ = await _drive_counts(
        db=db,
        default_branch=default_branch,
        dependency_provider=dependency_provider,
        changed_nodes=10,
        branch_name="profile_det_a",
        mutate_kind="peer",
    )
    second, _ = await _drive_counts(
        db=db,
        default_branch=default_branch,
        dependency_provider=dependency_provider,
        changed_nodes=10,
        branch_name="profile_det_b",
        mutate_kind="peer",
    )

    assert first.node_events == second.node_events
    assert first.expected_recompute == second.expected_recompute


async def test_merge_preserves_merged_data(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    """The recorder wiring must not alter what the merge writes to the graph."""
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    _, changed_ids = await _drive_counts(
        db=db,
        default_branch=default_branch,
        dependency_provider=dependency_provider,
        changed_nodes=10,
        branch_name="profile_data",
        mutate_kind="peer",
    )

    merged = await NodeManager.get_one(id=changed_ids[0], db=db)
    assert merged is not None
    assert merged.name.value.endswith("-edited")


async def test_rebase_cross_node_change_fans_out(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    """Rebase emits the same per-node fan-out as merge for an equivalent change."""
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    counts, _ = await _drive_counts(
        db=db,
        default_branch=default_branch,
        dependency_provider=dependency_provider,
        changed_nodes=10,
        branch_name="profile_rebase",
        operation="rebase",
        mutate_kind="peer",
    )

    assert counts.node_events == {"updated": 10}
    assert counts.expected_recompute == {COMPUTED_ATTRIBUTE: 10, DISPLAY_LABEL: 10, HFID: 0}
