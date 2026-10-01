from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.workflows.catalogue import PROFILE_REFRESH_MULTIPLE
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.graphql import graphql
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
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


async def _run_mutation(db: InfrahubDatabase, branch: Branch, query: str) -> WorkflowRecorder:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
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
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, test_case: RemovalTestCase
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
    )

    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    relationships = await profile.get_relationship(name=test_case.rel_name).get_relationships(db=db)
    assert [rel.peer_id for rel in relationships] == [peers[0].id]
    assert [
        (call["workflow"], call["parameters"]["branch_name"], sorted(call["parameters"]["node_ids"]))
        for call in workflow.submit_calls
    ] == [(PROFILE_REFRESH_MULTIPLE, default_branch.name, sorted([peers[1].id, peers[2].id]))]
