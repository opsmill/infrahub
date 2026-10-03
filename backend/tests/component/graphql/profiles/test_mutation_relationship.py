from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import MetadataOptions, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.workflows.catalogue import PROFILE_REFRESH_MULTIPLE
from infrahub.workflows.constants import WorkflowTag
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from collections import Counter

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

RELATIONSHIP_MUTATION = """
mutation Relationship($id: String!, $name: String!, $nodes: [RelatedNodeInput]!) {
    %(mutation)s(data: {id: $id, name: $name, nodes: $nodes}) { ok }
}
"""


@pytest.fixture
async def device_schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[DEVICE]), branch_name=default_branch.name)


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


async def _run_relationship_mutation(
    db: InfrahubDatabase,
    branch: Branch,
    account_session: AccountSession,
    mutation: str,
    profile_id: str,
    rel_name: str,
    peer_ids: list[str],
) -> WorkflowRecorder:
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
    assert result.errors is None
    return workflow


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
    if test_case.mutation == "RelationshipAdd":
        requested, changed = [peers[0], peers[1], peers[2]], [peers[1], peers[2]]
    else:
        requested, changed = [peers[0], peers[1]], [peers[0]]

    workflow = await _run_relationship_mutation(
        db=db,
        branch=default_branch,
        account_session=editor_session,
        mutation=test_case.mutation,
        profile_id=profile.id,
        rel_name=test_case.rel_name,
        peer_ids=[peer.id for peer in requested],
    )

    expected_context = EventContext(
        branch=EventBranchContext(name=default_branch.name, id=str(default_branch.uuid)),
        account_id=editor_session.account_id,
    )
    assert [
        (call["workflow"], call["parameters"], call["context"], call["tags"]) for call in workflow.submit_calls
    ] == [
        (
            PROFILE_REFRESH_MULTIPLE,
            {
                "branch_name": default_branch.name,
                "node_ids": sorted(peer.id for peer in changed)
                if test_case.mutation == "RelationshipRemove"
                else [peer.id for peer in changed],
                "context": expected_context,
            },
            expected_context,
            [
                WorkflowTag.BRANCH.render(identifier=default_branch.name),
                WorkflowTag.RELATED_NODE.render(identifier=profile.id),
            ],
        )
    ]
    # The request applies nothing itself: the peers it linked hold no profile value yet.
    for peer in changed:
        reloaded = await NodeManager.get_one(
            db=db, id=peer.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE, raise_on_error=True
        )
        assert reloaded.get_attribute(name="description").is_from_profile is False


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
    await _run_relationship_mutation(
        db=counting_db,
        branch=branch,
        account_session=account_session,
        mutation="RelationshipAdd",
        profile_id=profile.id,
        rel_name="related_nodes",
        peer_ids=[peer.id for peer in peers],
    )
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
