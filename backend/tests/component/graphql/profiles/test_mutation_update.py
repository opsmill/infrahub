from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

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
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from collections import Counter

    from infrahub.auth.session import AccountSession
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


@pytest.fixture
async def device_schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[DEVICE]), branch_name=default_branch.name)


async def _create_node(db: InfrahubDatabase, branch: Branch, kind: str, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


async def _run_mutation(
    db: InfrahubDatabase, branch: Branch, query: str, account_session: AccountSession | None = None
) -> WorkflowRecorder:
    gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=account_session)
    workflow = WorkflowRecorder()
    gql_params.context.service = await InfrahubServices.new(workflow=workflow)
    result = await graphql(
        schema=gql_params.schema, source=query, context_value=gql_params.context, root_value=None, variable_values={}
    )
    assert result.errors is None
    return workflow


@dataclass
class RemovalTestCase:
    name: str
    mutation: str
    rel_name: str
    peer_kind: str


REMOVAL_TEST_CASES: list[RemovalTestCase] = [
    RemovalTestCase(name="update_related_nodes", mutation="Update", rel_name="related_nodes", peer_kind="TestDevice"),
    RemovalTestCase(name="upsert_related_nodes", mutation="Upsert", rel_name="related_nodes", peer_kind="TestDevice"),
    RemovalTestCase(
        name="update_related_templates",
        mutation="Update",
        rel_name="related_templates",
        peer_kind="TemplateTestDevice",
    ),
    RemovalTestCase(
        name="upsert_related_templates",
        mutation="Upsert",
        rel_name="related_templates",
        peer_kind="TemplateTestDevice",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REMOVAL_TEST_CASES])
async def test_profile_update_refreshes_the_removed_peers(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema: None,
    session_admin: AccountSession,
    test_case: RemovalTestCase,
) -> None:
    profile = await _create_node(
        db=db, branch=default_branch, kind="ProfileTestDevice", profile_name="profile-1", profile_priority=10
    )
    name_field = "template_name" if test_case.peer_kind.startswith("Template") else "name"
    peers = [
        await _create_node(
            db=db, branch=default_branch, kind=test_case.peer_kind, profiles=[profile], **{name_field: f"peer-{idx}"}
        )
        for idx in range(3)
    ]

    workflow = await _run_mutation(
        db=db,
        branch=default_branch,
        query=f"""
        mutation {{
            ProfileTestDevice{test_case.mutation}(data: {{
                id: "{profile.id}",
                profile_name: {{ value: "profile-1" }},
                {test_case.rel_name}: [{{ id: "{peers[0].id}" }}]
            }}) {{ ok }}
        }}
        """,
        account_session=session_admin,
    )

    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    relationships = await profile.get_relationship(name=test_case.rel_name).get_relationships(db=db)
    assert [rel.peer_id for rel in relationships] == [peers[0].id]
    event_context = EventContext(
        branch=EventBranchContext(name=default_branch.name, id=str(default_branch.uuid)),
        account_id=session_admin.account_id,
    )
    assert [
        (
            call["workflow"],
            call["parameters"]["branch_name"],
            sorted(call["parameters"]["node_ids"]),
            call["parameters"]["context"],
            call["context"],
            call["tags"],
        )
        for call in workflow.submit_calls
    ] == [
        (
            PROFILE_REFRESH_MULTIPLE,
            default_branch.name,
            sorted([peers[1].id, peers[2].id]),
            event_context,
            event_context,
            [
                WorkflowTag.BRANCH.render(identifier=default_branch.name),
                WorkflowTag.RELATED_NODE.render(identifier=profile.id),
            ],
        )
    ]


@dataclass(frozen=True)
class CountedMutation:
    query_counts: Counter[str]
    row_counts: Counter[str]
    workflow: WorkflowRecorder


async def _rename_profile(
    db: InfrahubDatabase, branch: Branch, mutation: str, profile: Node, new_name: str
) -> CountedMutation:
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    workflow = await _run_mutation(
        db=counting_db,
        branch=branch,
        query=f"""
        mutation {{
            ProfileTestDevice{mutation}(data: {{ id: "{profile.id}", profile_name: {{ value: "{new_name}" }} }}) {{
                ok
            }}
        }}
        """,
    )
    return CountedMutation(query_counts=counting_db.query_counts, row_counts=counting_db.row_counts, workflow=workflow)


@dataclass
class RenameTestCase:
    name: str
    mutation: str


RENAME_TEST_CASES: list[RenameTestCase] = [
    RenameTestCase(name="update", mutation="Update"),
    RenameTestCase(name="upsert", mutation="Upsert"),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RENAME_TEST_CASES])
async def test_profile_update_without_peers_in_payload_does_not_read_them(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, test_case: RenameTestCase
) -> None:
    profiles: dict[int, Node] = {}
    for linked_nodes in (2, 6):
        profile = await _create_node(
            db=db,
            branch=default_branch,
            kind="ProfileTestDevice",
            profile_name=f"profile-{linked_nodes}",
            profile_priority=10,
        )
        for idx in range(linked_nodes):
            await _create_node(
                db=db, branch=default_branch, kind="TestDevice", name=f"device-{linked_nodes}-{idx}", profiles=[profile]
            )
        profiles[linked_nodes] = profile

    few = await _rename_profile(
        db=db, branch=default_branch, mutation=test_case.mutation, profile=profiles[2], new_name="renamed-2"
    )
    many = await _rename_profile(
        db=db, branch=default_branch, mutation=test_case.mutation, profile=profiles[6], new_name="renamed-6"
    )

    assert many.row_counts == few.row_counts
    assert many.query_counts == few.query_counts
    assert few.workflow.submit_calls == []
    assert many.workflow.submit_calls == []
    renamed = await NodeManager.get_one(db=db, branch=default_branch, id=profiles[6].id, raise_on_error=True)
    assert renamed.profile_name.value == "renamed-6"
