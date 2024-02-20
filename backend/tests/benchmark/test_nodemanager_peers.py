import pytest

from infrahub.core import registry
from infrahub.core.manager import Node, NodeManager
from infrahub.core.relationship import RelationshipManager
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def test_account(db: InfrahubDatabase, default_branch, register_core_models_schema) -> Node:
    node = await Node.init(db=db, schema="CoreAccount", branch=default_branch)
    await node.new(db=db, name="test_account", password="")
    await node.save(db=db)

    return node


@pytest.fixture
async def relm(db: InfrahubDatabase, default_branch, register_core_models_schema, test_account) -> RelationshipManager:
    model = registry.schema.get(name="CoreAccount")
    rel_schema = model.get_relationship("member_of_groups")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=default_branch, at=Timestamp(), node=test_account, name="member_of_groups"
    )

    return relm


def test_nodemanager_querypeers(aio_benchmark, db: InfrahubDatabase, default_branch, test_account):
    model = registry.schema.get(name="CoreAccount")
    aio_benchmark(
        NodeManager().query_peers,
        db=db,
        ids=[test_account.id],
        schema=model.get_relationship("member_of_groups"),
        filters=[],
    )


def test_relationshipmanager_getpeer(aio_benchmark, db: InfrahubDatabase, default_branch, relm):
    aio_benchmark(relm.get_peers, db=db)
