from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch.tasks import merge_branch, rebase_branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.dependencies.registry import get_component_registry
from infrahub.profiles.data_reader import ProfileDataReader
from infrahub.profiles.node_applier import NodeProfilesApplier
from infrahub.profiles.replay import select_nodes_to_refresh
from infrahub.workers.dependencies import build_cache, build_component, build_database, build_event_service
from infrahub.workflows.catalogue import PROFILE_REFRESH_MULTIPLE, PROFILE_REFRESH_PROCESS
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.component import build_worker_component
from tests.helpers.dependency_override import override_dependency
from tests.helpers.schema import load_schema
from tests.helpers.workflow_override import override_workflow

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

SERVER_KIND = "TestServer"
SERVER = NodeSchema(
    name="Server",
    namespace="Test",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="role", kind="Text", optional=True),
    ],
)


@dataclass(frozen=True)
class ReplayDataset:
    branch: Branch
    profile_id: str
    refreshed_ids: list[str]
    """Servers linked to the profile before the branch, with the new value applied on the branch."""
    added_id: str
    """A server linked to the profile on the default branch after the branch was created."""


async def _create_server(db: InfrahubDatabase, branch: Branch, name: str, profile_id: str) -> Node:
    server = await Node.init(db=db, schema=SERVER_KIND, branch=branch)
    await server.new(db=db, name=name, profiles=[profile_id])
    await server.save(db=db)
    await _apply_profiles(db=db, branch=branch, node_id=server.id)
    return server


async def _apply_profiles(db: InfrahubDatabase, branch: Branch, node_id: str) -> None:
    node = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    applier = NodeProfilesApplier(db=db, branch=branch, profile_data_reader=ProfileDataReader(db=db, branch=branch))
    if fields := await applier.apply_profiles(node=node):
        await node.save(db=db, fields=fields)


async def _seed(db: InfrahubDatabase, default_branch: Branch, branch_name: str) -> ReplayDataset:
    """A profile changed and applied on a branch, and a server linked to it on the default branch since."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[SERVER]), branch_name=default_branch.name, update_db=True)
    profile = await Node.init(db=db, schema=f"Profile{SERVER_KIND}", branch=default_branch)
    await profile.new(db=db, profile_name="server-profile", profile_priority=1000, role="role-1")
    await profile.save(db=db)
    refreshed = [
        await _create_server(db=db, branch=default_branch, name=f"server-{idx}", profile_id=profile.id)
        for idx in range(2)
    ]
    branch = await create_branch(branch_name=branch_name, db=db)

    branch_profile = await NodeManager.get_one(db=db, id=profile.id, branch=branch, raise_on_error=True)
    branch_profile.get_attribute(name="role").value = "role-2"
    await branch_profile.save(db=db)
    for server in refreshed:
        await _apply_profiles(db=db, branch=branch, node_id=server.id)
    added = await _create_server(db=db, branch=default_branch, name="server-added", profile_id=profile.id)

    return ReplayDataset(
        branch=branch,
        profile_id=profile.id,
        refreshed_ids=[server.id for server in refreshed],
        added_id=added.id,
    )


def _context(default_branch: Branch) -> InfrahubContext:
    return InfrahubContext.init(
        branch=default_branch, account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE)
    )


def _replayed_profile_calls(workflow: WorkflowRecorder) -> list[dict[str, object]]:
    return [
        {key: call["parameters"][key] for key in ("branch_name", "profile_kind", "profile_id", "held_attribute_names")}
        for call in workflow.get_submit_calls_for(PROFILE_REFRESH_PROCESS)
    ]


async def test_select_nodes_to_refresh_keeps_the_nodes_without_the_value_from_the_profile(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """An equal value from another profile or from the user, or an older value, still needs the refresh."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[SERVER]), branch_name=default_branch.name, update_db=True)
    profile = await Node.init(db=db, schema=f"Profile{SERVER_KIND}", branch=default_branch)
    await profile.new(db=db, profile_name="server-profile", profile_priority=1000, role="role-1")
    await profile.save(db=db)
    old_value = await _create_server(db=db, branch=default_branch, name="old-value", profile_id=profile.id)
    profile.get_attribute(name="role").value = "role-2"
    await profile.save(db=db)
    held = await _create_server(db=db, branch=default_branch, name="held", profile_id=profile.id)
    winning_profile = await Node.init(db=db, schema=f"Profile{SERVER_KIND}", branch=default_branch)
    await winning_profile.new(db=db, profile_name="winning-profile", profile_priority=10, role="role-2")
    await winning_profile.save(db=db)
    other_source = await Node.init(db=db, schema=SERVER_KIND, branch=default_branch)
    await other_source.new(db=db, name="other-source", profiles=[profile.id, winning_profile.id])
    await other_source.save(db=db)
    await _apply_profiles(db=db, branch=default_branch, node_id=other_source.id)
    user_set = await Node.init(db=db, schema=SERVER_KIND, branch=default_branch)
    await user_set.new(db=db, name="user-set", role="role-2", profiles=[profile.id])
    await user_set.save(db=db)

    node_ids = await select_nodes_to_refresh(
        db=db,
        branch_name=default_branch.name,
        profile_id=profile.id,
        node_ids=[old_value.id, held.id, other_source.id, user_set.id],
        attribute_names=["role"],
    )

    assert node_ids == [old_value.id, other_source.id, user_set.id]


async def test_merge_submits_the_refresh_of_the_profile_for_the_nodes_without_its_value(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    dataset = await _seed(db=db, default_branch=default_branch, branch_name="profile-merge")
    diff_coordinator = await get_component_registry().get_component(DiffCoordinator, db=db, branch=dataset.branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=dataset.branch)
    workflow = WorkflowRecorder()
    events = MemoryInfrahubEvent()
    cache = MemoryCache()
    component = await build_worker_component(db=db, cache=cache)

    with (
        override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider),  # noqa: ARG005
        override_dependency(build_event_service, lambda: events, dependency_provider=dependency_provider),
        override_workflow(workflow, dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
        override_dependency(build_component, lambda: component, dependency_provider=dependency_provider),
    ):
        await merge_branch(branch=dataset.branch.name, context=_context(default_branch=default_branch))

    assert workflow.get_submit_calls_for(PROFILE_REFRESH_MULTIPLE) == []
    assert _replayed_profile_calls(workflow=workflow) == [
        {
            "branch_name": default_branch.name,
            "profile_kind": f"Profile{SERVER_KIND}",
            "profile_id": dataset.profile_id,
            "held_attribute_names": ["role"],
        }
    ]
    assert await select_nodes_to_refresh(
        db=db,
        branch_name=default_branch.name,
        profile_id=dataset.profile_id,
        node_ids=[*dataset.refreshed_ids, dataset.added_id],
        attribute_names=["role"],
    ) == [dataset.added_id]


async def test_rebase_submits_the_refresh_of_the_profile_for_the_nodes_without_its_value(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    dataset = await _seed(db=db, default_branch=default_branch, branch_name="profile-rebase")
    workflow = WorkflowRecorder()
    events = MemoryInfrahubEvent()
    cache = MemoryCache()

    with (
        override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider),  # noqa: ARG005
        override_dependency(build_event_service, lambda: events, dependency_provider=dependency_provider),
        override_workflow(workflow, dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
    ):
        await rebase_branch(
            branch=dataset.branch.name, context=_context(default_branch=default_branch), send_events=True
        )

    assert workflow.get_submit_calls_for(PROFILE_REFRESH_MULTIPLE) == []
    assert _replayed_profile_calls(workflow=workflow) == [
        {
            "branch_name": dataset.branch.name,
            "profile_kind": f"Profile{SERVER_KIND}",
            "profile_id": dataset.profile_id,
            "held_attribute_names": ["role"],
        }
    ]
    assert await select_nodes_to_refresh(
        db=db,
        branch_name=dataset.branch.name,
        profile_id=dataset.profile_id,
        node_ids=[*dataset.refreshed_ids, dataset.added_id],
        attribute_names=["role"],
    ) == [dataset.added_id]
