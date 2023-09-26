import pytest

from infrahub.core import registry
from infrahub.core.artifact import CoreArtifactDefinition
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
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
async def group01(db: InfrahubDatabase, default_branch: Branch, car_person_data_generic):
    obj = await Node.init(db=db, schema="CoreStandardGroup")
    await obj.new(db=db, name="group01", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]])
    await obj.save(db=db)
    return obj


@pytest.fixture
async def transform01(db: InfrahubDatabase, default_branch: Branch, car_person_data_generic):
    obj = await Node.init(db=db, schema="CoreTransformPython")
    await obj.new(
        db=db,
        name="transform01",
        query=str(car_person_data_generic["q1"].id),
        url="mytransform",
        repository=str(car_person_data_generic["r1"].id),
        file_path="transform01.py",
        class_name="Transform01",
        rebase=False,
    )
    await obj.save(db=db)
    return obj


@pytest.fixture
async def definition01(
    db: InfrahubDatabase, default_branch: Branch, group01: Node, transform01: Node
) -> CoreArtifactDefinition:
    obj = await CoreArtifactDefinition.init(db=db, schema="CoreArtifactDefinition")
    await obj.new(
        db=db,
        name="artifactdef01",
        targets=group01,
        transformation=transform01,
        content_type="application/json",
        artifact_name="myartifact",
        parameters='{"name": "name__value"}',
    )
    await obj.save(db=db)
    return obj


async def test_artifact_generate_first_time(
    db: InfrahubDatabase, default_branch: Branch, rpc_client, definition01: CoreArtifactDefinition
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

    nodes = await definition01.generate(db=db, rpc_client=rpc_client)
    assert len(nodes) == 2

    artifacts = await registry.manager.query(db=db, schema="CoreArtifact")
    assert len(artifacts) == 2


async def test_artifact_generate_existing_artifact(
    db: InfrahubDatabase,
    default_branch: Branch,
    rpc_client,
    car_person_data_generic,
    definition01: CoreArtifactDefinition,
):
    a1 = await Node.init(db=db, schema="CoreArtifact")
    await a1.new(
        db=db,
        name=definition01.artifact_name.value,
        definition=str(definition01.id),
        content_type=definition01.content_type.value,
        object=str(car_person_data_generic["c1"].id),
        status="Ready",
    )
    await a1.save(db=db)

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

    nodes = await definition01.generate(db=db, rpc_client=rpc_client)
    assert len(nodes) == 2

    artifacts = await registry.manager.query(db=db, schema="CoreArtifact")
    assert len(artifacts) == 2
