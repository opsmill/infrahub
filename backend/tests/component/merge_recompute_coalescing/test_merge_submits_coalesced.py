"""The merge and rebase post-process submit one coalesced recompute, not per-node fan-out."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import merge_branch, rebase_branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.dependencies.registry import get_component_registry
from infrahub.workers.dependencies import (
    build_cache,
    build_component,
    build_database,
    build_event_service,
    build_workflow,
)
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    DISPLAY_LABELS_PROCESS_JINJA2,
    HFID_PROCESS,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.component import build_worker_component
from tests.helpers.merge_recompute.dataset import (
    PROFILE_NODE_KIND,
    PROFILE_PEER_KIND,
    build_profile_schema,
    load_profile_schema,
    seed_branch,
)
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_merge_submits_one_coalesced_recompute_per_target(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    changed_nodes = 8
    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name="coalesced_merge",
        changed_nodes=changed_nodes,
        mutate_target="branch",
        mutate_kind="peer",
    )

    # The merge flow loads the tracked diff, so it must be enriched under the branch tracking id first.
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=seeded.branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=seeded.branch)

    workflow_recorder = WorkflowRecorder()
    event_recorder = MemoryInfrahubEvent()
    cache = MemoryCache()
    component = await build_worker_component(db=db, cache=cache)
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )

    # Captured before the merge so it can be compared against what the merge stamps on the source branch.
    pre_merge_destination_changed_at = default_branch.schema_changed_at
    assert pre_merge_destination_changed_at is not None

    with (
        dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
        dependency_provider.scope(build_event_service, lambda: event_recorder),
        dependency_provider.scope(build_workflow, lambda: workflow_recorder),
        dependency_provider.scope(build_cache, lambda: cache),
        dependency_provider.scope(build_component, lambda: component),
    ):
        await merge_branch(branch=seeded.branch_name, context=context)

    # The merge stamps the source branch with the destination's pre-merge schema_changed_at, the value
    # an out-of-process recovery restores after rolling a crashed merge back.
    merged_source = await Branch.get_by_name(db=db, name=seeded.branch_name)
    assert merged_source.pre_merge_destination_schema_changed_at == pre_merge_destination_changed_at

    computed = workflow_recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_JINJA2)
    display = workflow_recorder.get_submit_calls_for(DISPLAY_LABELS_PROCESS_JINJA2)
    hfid = workflow_recorder.get_submit_calls_for(HFID_PROCESS)

    # The computed attribute and display label recompute once each over the union of changed peers;
    # the human-friendly id reads only the local name, so a peer change does not fan out to it. The
    # exact target shape is covered by the unit submission tests.
    assert len(computed) == 1
    assert len(display) == 1
    assert hfid == []

    # A merge recomputes on the destination branch.
    assert computed[0]["parameters"]["branch_name"] == default_branch.name
    assert display[0]["parameters"]["branch_name"] == default_branch.name


async def test_rebase_submits_one_coalesced_recompute_per_target(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    changed_nodes = 6
    # Rebase replays the default branch's intervening changes, so the peers are mutated on default.
    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name="coalesced_rebase",
        changed_nodes=changed_nodes,
        mutate_target="default",
        mutate_kind="peer",
    )

    workflow_recorder = WorkflowRecorder()
    event_recorder = MemoryInfrahubEvent()
    cache = MemoryCache()
    component = await build_worker_component(db=db, cache=cache)
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )

    with (
        dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
        dependency_provider.scope(build_event_service, lambda: event_recorder),
        dependency_provider.scope(build_workflow, lambda: workflow_recorder),
        dependency_provider.scope(build_cache, lambda: cache),
        dependency_provider.scope(build_component, lambda: component),
    ):
        await rebase_branch(branch=seeded.branch_name, context=context, send_events=True)

    computed = workflow_recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_JINJA2)
    display = workflow_recorder.get_submit_calls_for(DISPLAY_LABELS_PROCESS_JINJA2)
    hfid = workflow_recorder.get_submit_calls_for(HFID_PROCESS)

    assert len(computed) == 1
    assert len(display) == 1
    assert hfid == []

    # A rebase recomputes on the user branch, not the destination.
    assert computed[0]["parameters"]["branch_name"] == seeded.branch_name
    assert display[0]["parameters"]["branch_name"] == seeded.branch_name


async def test_merge_delete_peer_coalesces_reader_recompute_by_own_id(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)

    # Optional peer so it can be deleted while the reader survives.
    schema = build_profile_schema()
    node_schema = next(node for node in schema.nodes if node.kind == PROFILE_NODE_KIND)
    node_schema.relationships[0].optional = True
    await load_schema(db=db, schema=schema, update_db=True)

    peer = await Node.init(db=db, schema=PROFILE_PEER_KIND, branch=default_branch)
    await peer.new(db=db, name="beta")
    await peer.save(db=db)
    # Several readers of the same peer, to prove the deletion coalesces them rather than fanning out.
    reader_ids: list[str] = []
    for index in range(3):
        reader = await Node.init(db=db, schema=PROFILE_NODE_KIND, branch=default_branch)
        await reader.new(db=db, name=f"reader-{index}", peer=peer)
        await reader.save(db=db)
        reader_ids.append(reader.id)

    branch = await create_branch(branch_name="delete-peer-submit", db=db)
    peer_on_branch = await NodeManager.get_one(id=peer.id, db=db, branch=branch)
    assert peer_on_branch is not None
    await peer_on_branch.delete(db=db)

    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

    recorder = WorkflowRecorder()
    event_recorder = MemoryInfrahubEvent()
    cache = MemoryCache()
    component = await build_worker_component(db=db, cache=cache)
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with (
        dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
        dependency_provider.scope(build_event_service, lambda: event_recorder),
        dependency_provider.scope(build_workflow, lambda: recorder),
        dependency_provider.scope(build_cache, lambda: cache),
        dependency_provider.scope(build_component, lambda: component),
    ):
        await merge_branch(branch=branch.name, context=context)

    # The reverse lookup from the deleted peer finds no readers once its edges close, so the readers
    # must be recomputed by their own ids, coalesced into one submission per family.
    for workflow in (COMPUTED_ATTRIBUTE_PROCESS_JINJA2, DISPLAY_LABELS_PROCESS_JINJA2):
        own_id_submissions = [
            call
            for call in recorder.get_submit_calls_for(workflow)
            if call["parameters"]["node_kind"] == PROFILE_NODE_KIND
        ]
        assert len(own_id_submissions) == 1, f"{workflow.name} fanned out instead of coalescing the readers"
        assert sorted(own_id_submissions[0]["parameters"]["object_ids"]) == sorted(reader_ids)
