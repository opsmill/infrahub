from infrahub.core import registry
from infrahub.core.manager import Node, NodeManager
from infrahub.core.relationship import RelationshipManager
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_nodemanager_querypeers(benchmark, db: InfrahubDatabase, default_branch, register_core_models_schema):
    node = await Node.init(db=db, schema="CoreAccount", branch=default_branch)
    await node.new(db=db, name="test_account", password="")
    await node.save(db=db)

    model = registry.schema.get(name="CoreAccount")
    await benchmark(
        NodeManager().query_peers,
        db=db,
        ids=[node.id],
        schema=model.get_relationship("member_of_groups"),
        filters=[],
    )


async def test_relationshipmanager_getpeer(
    benchmark, db: InfrahubDatabase, default_branch, register_core_models_schema
):
    node = await Node.init(db=db, schema="CoreAccount", branch=default_branch)
    await node.new(db=db, name="test_account", password="")
    await node.save(db=db)

    model = registry.schema.get(name="CoreAccount")
    rel_schema = model.get_relationship("member_of_groups")

    relm = await RelationshipManager.init(
        db=db, schema=rel_schema, branch=default_branch, at=Timestamp(), node=node, name="member_of_groups"
    )

    await benchmark(relm.get_peers, db=db)
