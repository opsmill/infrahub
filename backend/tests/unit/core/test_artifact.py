import pytest
from neo4j import AsyncSession

from infrahub.core import registry
from infrahub.core.artifact import CoreArtifactDefinition
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.message_bus.events import (
    ArtifactMessageAction,
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
)
from infrahub.message_bus.rpc import InfrahubRpcClientTesting

# pylint: disable=unused-argument


@pytest.fixture
async def rpc_client():
    rpc_client = await InfrahubRpcClientTesting().connect()
    return rpc_client


@pytest.fixture
async def group01(session: AsyncSession, default_branch: Branch, car_person_data_generic):
    obj = await Node.init(session=session, schema="CoreStandardGroup")
    await obj.new(
        session=session, name="group01", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]]
    )
    await obj.save(session=session)
    return obj


@pytest.fixture
async def transform01(session: AsyncSession, default_branch: Branch, car_person_data_generic):
    obj = await Node.init(session=session, schema="CoreTransformPython")
    await obj.new(
        session=session,
        name="transform01",
        query=str(car_person_data_generic["q1"].id),
        url="mytransform",
        repository=str(car_person_data_generic["r1"].id),
        file_path="transform01.py",
        class_name="Transform01",
        rebase=False,
    )
    await obj.save(session=session)
    return obj


@pytest.fixture
async def definition01(
    session: AsyncSession, default_branch: Branch, group01: Node, transform01: Node
) -> CoreArtifactDefinition:
    obj = await CoreArtifactDefinition.init(session=session, schema="CoreArtifactDefinition")
    await obj.new(
        session=session,
        name="artifactdef01",
        targets=group01,
        transformation=transform01,
        content_type="application/json",
        artifact_name="myartifact",
        parameters='{"name": "name__value"}',
    )
    await obj.save(session=session)
    return obj


async def test_artifact_generate(
    session: AsyncSession, default_branch: Branch, rpc_client, definition01: CoreArtifactDefinition
):
    mock_response = InfrahubRPCResponse(
        status=RPCStatusCode.OK,
        response={"artifact_id": "XXXXX", "changed": True, "checksum": "YYYYYY", "storage_id": "DDDDDDDDDD"},
    )
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.ARTIFACT, action=ArtifactMessageAction.GENERATE
    )
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.ARTIFACT, action=ArtifactMessageAction.GENERATE
    )

    nodes = await definition01.generate(session=session, rpc_client=rpc_client)
    assert len(nodes) == 2

    artifacts = await registry.manager.query(session=session, schema="CoreArtifact")
    assert len(artifacts) == 2
