from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from structlog.testing import capture_logs

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import MetadataOptions, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.profiles.data_reader import ProfileDataReader
from infrahub.profiles.node_applier import NodeProfilesApplier
from infrahub.services import InfrahubServices
from infrahub.workflows.catalogue import PROFILE_REFRESH_MULTIPLE
from infrahub.workflows.constants import WorkflowTag
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import ContextRecordingWorkflow, WorkflowRecorder
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from collections import Counter

    from graphql import ExecutionResult

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

DEVICE = NodeSchema(
    name="Device",
    namespace="Test",
    generate_template=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="description", kind="Text", optional=True),
    ],
)

SERVER = NodeSchema(
    name="Server",
    namespace="Test",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="role", kind="Text"),
    ],
)

RELATIONSHIP_MUTATION = """
mutation Relationship($id: String!, $name: String!, $nodes: [RelatedNodeInput]!) {
    %(mutation)s(data: {id: $id, name: $name, nodes: $nodes}) { ok }
}
"""


@pytest.fixture
async def device_schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[DEVICE]), branch_name=default_branch.name)


@pytest.fixture
async def server_schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[SERVER]), branch_name=default_branch.name)


@pytest.fixture
async def editor_session(
    db: InfrahubDatabase, default_permission_backend: None, create_test_admin: Node
) -> AccountSession:
    await define_permissions(
        account=create_test_admin,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace="*",
                name="*",
                action=PermissionAction.ANY.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
        ],
    )
    return AccountSession(authenticated=True, auth_type=AuthType.API, account_id=create_test_admin.id)


async def _create_node(db: InfrahubDatabase, branch: Branch, kind: str, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


async def _apply_profile_values(db: InfrahubDatabase, branch: Branch, node_id: str) -> None:
    node = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    applier = NodeProfilesApplier(db=db, branch=branch, profile_data_reader=ProfileDataReader(db=db, branch=branch))
    await node.save(db=db, fields=await applier.apply_profiles(node=node))


async def _run_relationship_mutation(
    db: InfrahubDatabase,
    branch: Branch,
    account_session: AccountSession,
    mutation: str,
    profile_id: str,
    rel_name: str,
    peer_ids: list[str],
) -> tuple[ExecutionResult, WorkflowRecorder]:
    workflow = WorkflowRecorder()
    gql_params = await prepare_graphql_params(
        db=db, branch=branch, account_session=account_session, service=await InfrahubServices.new(workflow=workflow)
    )
    result = await graphql(
        schema=gql_params.schema,
        source=RELATIONSHIP_MUTATION % {"mutation": mutation},
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": profile_id, "name": rel_name, "nodes": [{"id": peer_id} for peer_id in peer_ids]},
    )
    return result, workflow


@dataclass
class PeerChangeTestCase:
    name: str
    mutation: str
    rel_name: str
    peer_kind: str


PEER_CHANGE_TEST_CASES: list[PeerChangeTestCase] = [
    PeerChangeTestCase(
        name="add_related_nodes", mutation="RelationshipAdd", rel_name="related_nodes", peer_kind="TestDevice"
    ),
    PeerChangeTestCase(
        name="add_related_templates",
        mutation="RelationshipAdd",
        rel_name="related_templates",
        peer_kind="TemplateTestDevice",
    ),
    PeerChangeTestCase(
        name="remove_related_nodes", mutation="RelationshipRemove", rel_name="related_nodes", peer_kind="TestDevice"
    ),
    PeerChangeTestCase(
        name="remove_related_templates",
        mutation="RelationshipRemove",
        rel_name="related_templates",
        peer_kind="TemplateTestDevice",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PEER_CHANGE_TEST_CASES])
async def test_profile_peer_change_submits_the_refresh_of_the_changed_peers(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema: None,
    editor_session: AccountSession,
    test_case: PeerChangeTestCase,
) -> None:
    """The request only links or unlinks the peers; the refresh flows apply or remove the profile values."""
    name_field = "template_name" if test_case.peer_kind.startswith("Template") else "name"
    peers = [
        await _create_node(db=db, branch=default_branch, kind=test_case.peer_kind, **{name_field: f"peer-{idx}"})
        for idx in range(3)
    ]
    # The first peer is linked already, so an add leaves it alone and a remove takes it with the second one.
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        description="from-profile",
        **{test_case.rel_name: [peers[0]]},
    )
    await _apply_profile_values(db=db, branch=default_branch, node_id=peers[0].id)
    if test_case.mutation == "RelationshipAdd":
        requested, changed, description = [peers[0], peers[1], peers[2]], [peers[1], peers[2]], (None, False)
    else:
        requested, changed, description = [peers[0], peers[1]], [peers[0]], ("from-profile", True)

    result, workflow = await _run_relationship_mutation(
        db=db,
        branch=default_branch,
        account_session=editor_session,
        mutation=test_case.mutation,
        profile_id=profile.id,
        rel_name=test_case.rel_name,
        peer_ids=[peer.id for peer in requested],
    )

    assert result.errors is None
    expected_context = EventContext(
        branch=EventBranchContext(name=default_branch.name, id=str(default_branch.uuid)),
        account_id=editor_session.account_id,
    )
    assert [(call["workflow"], call["parameters"], call["tags"]) for call in workflow.submit_calls] == [
        (
            PROFILE_REFRESH_MULTIPLE,
            {
                "branch_name": default_branch.name,
                "node_ids": sorted(peer.id for peer in changed),
                "context": expected_context,
            },
            [
                WorkflowTag.BRANCH.render(identifier=default_branch.name),
                WorkflowTag.RELATED_NODE.render(identifier=profile.id),
            ],
        )
    ]
    reloaded = await NodeManager.get_many(
        db=db, ids=[peer.id for peer in changed], branch=default_branch, include_metadata=MetadataOptions.SOURCE
    )
    assert [
        (
            reloaded[peer.id].get_attribute(name="description").value,
            reloaded[peer.id].get_attribute(name="description").is_from_profile,
        )
        for peer in changed
    ] == [description] * len(changed)


async def _count_relationship_add(
    db: InfrahubDatabase, branch: Branch, account_session: AccountSession, peer_count: int
) -> Counter[str]:
    peers = [
        await _create_node(db=db, branch=branch, kind="TestDevice", name=f"device-{peer_count}-{idx}")
        for idx in range(peer_count)
    ]
    profile = await _create_node(
        db=db,
        branch=branch,
        kind="ProfileTestDevice",
        profile_name=f"profile-{peer_count}",
        profile_priority=10,
        description="from-profile",
    )
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    result, _ = await _run_relationship_mutation(
        db=counting_db,
        branch=branch,
        account_session=account_session,
        mutation="RelationshipAdd",
        profile_id=profile.id,
        rel_name="related_nodes",
        peer_ids=[peer.id for peer in peers],
    )
    assert result.errors is None
    return counting_db.query_counts


async def test_relationship_add_to_a_profile_runs_no_profile_query_per_added_node(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, editor_session: AccountSession
) -> None:
    few = await _count_relationship_add(db=db, branch=default_branch, account_session=editor_session, peer_count=2)
    many = await _count_relationship_add(db=db, branch=default_branch, account_session=editor_session, peer_count=6)

    growth = {name: many[name] - few[name] for name in many.keys() | few.keys() if many[name] != few[name]}
    # Four more peers cost four relationship writes and four peer reads, as any RelationshipAdd does.
    assert growth == {"node_list_get_attribute": 4, "node_list_get_info": 4, "relationship_create": 4}
    assert few["profile_get_data"] == 0


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PEER_CHANGE_TEST_CASES])
async def test_profile_peer_change_succeeds_when_the_refresh_submission_fails(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema: None,
    editor_session: AccountSession,
    test_case: PeerChangeTestCase,
) -> None:
    name_field = "template_name" if test_case.peer_kind.startswith("Template") else "name"
    peer = await _create_node(db=db, branch=default_branch, kind=test_case.peer_kind, **{name_field: "peer-0"})
    linked = [peer] if test_case.mutation == "RelationshipRemove" else []
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        **{test_case.rel_name: linked},
    )
    events = MemoryInfrahubEvent()
    workflow = ContextRecordingWorkflow()
    workflow.failures.append(RuntimeError(f"{PROFILE_REFRESH_MULTIPLE.name} submission rejected"))
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=editor_session,
        service=await InfrahubServices.new(workflow=workflow, event=events),
    )

    with capture_logs() as records:
        result = await graphql(
            schema=gql_params.schema,
            source=RELATIONSHIP_MUTATION % {"mutation": test_case.mutation},
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": profile.id, "name": test_case.rel_name, "nodes": [{"id": peer.id}]},
        )
    assert gql_params.context.background
    await gql_params.context.background()

    assert result.errors is None
    assert result.data == {test_case.mutation: {"ok": True}}
    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    relationships = await profile.get_relationship(name=test_case.rel_name).get_relationships(db=db)
    assert [rel.peer_id for rel in relationships] == ([] if linked else [peer.id])
    assert [(record["log_level"], record["event"]) for record in records if record["log_level"] == "error"] == [
        ("error", f"Failed to submit the profile refresh of the peers of {profile.id}")
    ]
    assert [(type(event), event.node_id) for event in events.events] == [
        (NodeUpdatedEvent, profile.id),
        (NodeUpdatedEvent, peer.id),
    ]


async def test_relationship_remove_refuses_a_node_that_inherits_a_required_value_from_the_profile(
    db: InfrahubDatabase, default_branch: Branch, server_schema: None, editor_session: AccountSession
) -> None:
    """The refresh flow could not clear the value, so the request refuses the removal before it commits."""
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestServer",
        profile_name="profile-1",
        profile_priority=10,
        role="from-profile",
    )
    server = await _create_node(db=db, branch=default_branch, kind="TestServer", name="server-1", profiles=[profile])
    await _apply_profile_values(db=db, branch=default_branch, node_id=server.id)

    result, workflow = await _run_relationship_mutation(
        db=db,
        branch=default_branch,
        account_session=editor_session,
        mutation="RelationshipRemove",
        profile_id=profile.id,
        rel_name="related_nodes",
        peer_ids=[server.id],
    )

    assert result.errors is not None
    assert [error.message for error in result.errors] == [
        f"Cannot remove profile '{profile.id}' because node 'TestServer(ID: {server.id})' (ID: {server.id}) "
        "inherits required attribute 'role' from this profile."
    ]
    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    assert [rel.peer_id for rel in await profile.get_relationship(name="related_nodes").get_relationships(db=db)] == [
        server.id
    ]
    assert workflow.submit_calls == []
