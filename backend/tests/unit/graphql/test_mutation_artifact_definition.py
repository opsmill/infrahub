from typing import Dict

import pytest
from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params
from infrahub.message_bus import messages
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


@pytest.fixture
async def group1(db: InfrahubDatabase, default_branch: Branch, car_person_data_generic: Dict[str, Node]) -> Node:
    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]])
    await g1.save(db=db)
    return g1


@pytest.fixture
async def transformation1(
    db: InfrahubDatabase, default_branch: Branch, car_person_data_generic: Dict[str, Node]
) -> Node:
    t1 = await Node.init(db=db, schema="CoreTransformPython")
    await t1.new(
        db=db,
        name="transform01",
        query=str(car_person_data_generic["q1"].id),
        repository=str(car_person_data_generic["r1"].id),
        file_path="transform01.py",
        class_name="Transform01",
        rebase=False,
    )
    await t1.save(db=db)
    return t1


@pytest.fixture
async def definition1(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_data_generic: Dict[str, Node],
    group1: Node,
    transformation1: Node,
) -> Node:
    ad1 = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
    await ad1.new(
        db=db,
        name="artifactdef01",
        targets=group1,
        transformation=transformation1,
        content_type="application/json",
        artifact_name="myartifact",
        parameters='{"name": "name__value"}',
    )
    await ad1.save(db=db)
    return ad1


async def test_create_artifact_definition(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema,
    car_person_data_generic,
    group1: Node,
    transformation1: Node,
    branch: Branch,
):
    rpc_client = InfrahubRpcClientTesting()

    query = """
    mutation {
        CoreArtifactDefinitionCreate(data: {
            name: { value: "Artifact 01"},
            artifact_name: { value: "myartifact"},
            parameters: { value: { name: "name__value"}},
            content_type: { value: "application/json"},
            targets: { id: "%s"},
            transformation: { id: "%s"},
        }) {
            ok
            object {
                id
            }
        }
    }
    """ % (
        group1.id,
        transformation1.id,
    )
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch, rpc_client=rpc_client)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["CoreArtifactDefinitionCreate"]["ok"] is True
    ad_id = result.data["CoreArtifactDefinitionCreate"]["object"]["id"]

    ad1 = await NodeManager.get_one(db=db, id=ad_id, include_owner=True, include_source=True, branch=branch)

    assert ad1.name.value == "Artifact 01"

    assert (
        messages.RequestArtifactDefinitionGenerate(artifact_definition=ad_id, branch=branch.name, limit=[])
        in rpc_client.sent
    )


async def test_update_artifact_definition(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema,
    car_person_data_generic,
    definition1: Node,
    branch: Branch,
):
    rpc_client = InfrahubRpcClientTesting()

    query = """
    mutation {
        CoreArtifactDefinitionUpdate(data: {
            id: "%s",
            artifact_name: { value: "myartifact2"},
        }) {
            ok
            object {
                id
            }
        }
    }
    """ % (definition1.id)

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch, rpc_client=rpc_client)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["CoreArtifactDefinitionUpdate"]["ok"] is True

    ad1_post = await NodeManager.get_one(
        db=db, id=definition1.id, include_owner=True, include_source=True, branch=branch
    )

    assert ad1_post.artifact_name.value == "myartifact2"

    assert (
        messages.RequestArtifactDefinitionGenerate(artifact_definition=definition1.id, branch=branch.name, limit=[])
        in rpc_client.sent
    )
