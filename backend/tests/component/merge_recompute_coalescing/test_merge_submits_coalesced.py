"""The merge and rebase post-process submit one coalesced recompute, not per-node fan-out."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import merge_branch, rebase_branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.events.branch_action import BranchRebasedEvent
from infrahub.events.node_action import NodeCreatedEvent, NodeMutatedEvent, NodeUpdatedEvent
from infrahub.workers.dependencies import (
    build_cache,
    build_component,
    build_database,
    build_event_service,
)
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    DISPLAY_LABELS_PROCESS_JINJA2,
    HFID_PROCESS,
    PROFILE_REFRESH_MULTIPLE,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.component import build_worker_component
from tests.helpers.dependency_override import override_dependency
from tests.helpers.merge_recompute.dataset import (
    PROFILE_NODE_KIND,
    PROFILE_PEER_KIND,
    build_profile_schema,
    load_profile_schema,
    seed_branch,
)
from tests.helpers.schema import load_schema
from tests.helpers.workflow_override import override_workflow

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
        override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider),  # noqa: ARG005
        override_dependency(build_event_service, lambda: event_recorder, dependency_provider=dependency_provider),
        override_workflow(workflow_recorder, dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
        override_dependency(build_component, lambda: component, dependency_provider=dependency_provider),
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


async def test_rebase_replays_the_branch_changes_onto_the_new_base(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    # The default branch renames every peer after the fork, so the branch's own values read the old names.
    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name="replayed_rebase",
        changed_nodes=6,
        mutate_target="default",
        mutate_kind="peer",
    )
    renamed_node = await NodeManager.get_one(db=db, id=seeded.main_ids[0], branch=seeded.branch)
    renamed_node.get_attribute(name="name").value = "replayed_rebase-node-renamed"
    await renamed_node.save(db=db)
    created_node = await Node.init(db=db, schema=PROFILE_NODE_KIND, branch=seeded.branch)
    await created_node.new(db=db, name="replayed_rebase-node-created", peer=seeded.peer_ids[1])
    await created_node.save(db=db)

    workflow_recorder = WorkflowRecorder()
    event_recorder = MemoryInfrahubEvent()
    cache = MemoryCache()
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )

    with (
        override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider),  # noqa: ARG005
        override_dependency(build_event_service, lambda: event_recorder, dependency_provider=dependency_provider),
        override_workflow(workflow_recorder, dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
    ):
        await rebase_branch(branch=seeded.branch_name, context=context, send_events=True)

    assert [type(event) for event in event_recorder.events if not isinstance(event, NodeMutatedEvent)] == [
        BranchRebasedEvent
    ]
    replayed_nodes = {
        event.node_id: type(event) for event in event_recorder.events if isinstance(event, NodeMutatedEvent)
    }
    assert replayed_nodes == {renamed_node.id: NodeUpdatedEvent, created_node.id: NodeCreatedEvent}

    # A rebase recomputes on the user branch, and every value the branch's changes derived is recomputed by id.
    for workflow in (COMPUTED_ATTRIBUTE_PROCESS_JINJA2, DISPLAY_LABELS_PROCESS_JINJA2, HFID_PROCESS):
        submissions = workflow_recorder.get_submit_calls_for(workflow)
        assert [
            (call["parameters"]["branch_name"], call["parameters"]["node_kind"], set(call["parameters"]["object_ids"]))
            for call in submissions
        ] == [(seeded.branch_name, PROFILE_NODE_KIND, {renamed_node.id, created_node.id})]


async def test_rebase_replays_the_default_branch_changes_to_kinds_the_branch_changed(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name="schema_rebase",
        changed_nodes=3,
        mutate_target="default",
        mutate_kind="peer",
    )
    # The branch makes the node's human-friendly id read its peer, the peer kind keeps the default branch's schema
    await load_schema(
        db=db,
        schema=build_profile_schema(cross_relationship_hfid=True),
        branch_name=seeded.branch_name,
        update_db=True,
        limit=[PROFILE_NODE_KIND],
    )
    default_branch_node = await Node.init(db=db, schema=PROFILE_NODE_KIND, branch=default_branch)
    await default_branch_node.new(db=db, name="schema_rebase-node-default", peer=seeded.peer_ids[0])
    await default_branch_node.save(db=db)

    workflow_recorder = WorkflowRecorder()
    event_recorder = MemoryInfrahubEvent()
    cache = MemoryCache()
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )

    with (
        override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider),  # noqa: ARG005
        override_dependency(build_event_service, lambda: event_recorder, dependency_provider=dependency_provider),
        override_workflow(workflow_recorder, dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
    ):
        await rebase_branch(branch=seeded.branch_name, context=context, send_events=True)

    # the peers the default branch renamed keep the default branch's schema, so they are not replayed
    branch_node_schema = registry.schema.get_node_schema(name=PROFILE_NODE_KIND, branch=seeded.branch_name)
    replayed_nodes = {
        (event.kind, event.node_id): type(event)
        for event in event_recorder.events
        if isinstance(event, NodeMutatedEvent)
    }
    assert replayed_nodes == {
        ("SchemaNode", branch_node_schema.id): NodeUpdatedEvent,
        (PROFILE_NODE_KIND, default_branch_node.id): NodeCreatedEvent,
    }
    for workflow in (COMPUTED_ATTRIBUTE_PROCESS_JINJA2, DISPLAY_LABELS_PROCESS_JINJA2, HFID_PROCESS):
        submissions = workflow_recorder.get_submit_calls_for(workflow)
        assert [
            (call["parameters"]["branch_name"], call["parameters"]["node_kind"], set(call["parameters"]["object_ids"]))
            for call in submissions
        ] == [(seeded.branch_name, PROFILE_NODE_KIND, {default_branch_node.id})]


async def test_rebase_refreshes_the_profiles_assigned_on_the_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)
    profile = await Node.init(db=db, schema=f"Profile{PROFILE_NODE_KIND}", branch=default_branch)
    await profile.new(db=db, profile_name="replayed-profile", profile_priority=1000)
    await profile.save(db=db)

    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name="profile_rebase",
        changed_nodes=2,
        mutate_target="default",
        mutate_kind="peer",
    )
    profiled_node = await NodeManager.get_one(db=db, id=seeded.main_ids[0], branch=seeded.branch)
    await profiled_node.profiles.update(db=db, data=[profile])
    await profiled_node.save(db=db)

    workflow_recorder = WorkflowRecorder()
    event_recorder = MemoryInfrahubEvent()
    cache = MemoryCache()
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )

    with (
        override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider),  # noqa: ARG005
        override_dependency(build_event_service, lambda: event_recorder, dependency_provider=dependency_provider),
        override_workflow(workflow_recorder, dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
    ):
        await rebase_branch(branch=seeded.branch_name, context=context, send_events=True)

    assert [call["parameters"] for call in workflow_recorder.get_submit_calls_for(PROFILE_REFRESH_MULTIPLE)] == [
        {"branch_name": seeded.branch_name, "node_ids": [profiled_node.id]}
    ]


async def test_rebase_of_a_branch_without_changes_replays_nothing(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_profile_schema(db=db)

    seeded = await seed_branch(
        db=db,
        default_branch=default_branch,
        branch_name="unchanged_rebase",
        changed_nodes=6,
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
        override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider),  # noqa: ARG005
        override_dependency(build_event_service, lambda: event_recorder, dependency_provider=dependency_provider),
        override_workflow(workflow_recorder, dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
        override_dependency(build_component, lambda: component, dependency_provider=dependency_provider),
    ):
        await rebase_branch(branch=seeded.branch_name, context=context, send_events=True)

    rebased_branch = await Branch.get_by_name(db=db, name=seeded.branch_name)
    assert Timestamp(rebased_branch.get_branched_from()) > Timestamp(seeded.branch.get_branched_from())
    assert [type(event) for event in event_recorder.events] == [BranchRebasedEvent]
    assert workflow_recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_JINJA2) == []
    assert workflow_recorder.get_submit_calls_for(DISPLAY_LABELS_PROCESS_JINJA2) == []
    assert workflow_recorder.get_submit_calls_for(HFID_PROCESS) == []


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
        override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider),  # noqa: ARG005
        override_dependency(build_event_service, lambda: event_recorder, dependency_provider=dependency_provider),
        override_workflow(recorder, dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
        override_dependency(build_component, lambda: component, dependency_provider=dependency_provider),
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
