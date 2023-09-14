from neo4j import AsyncSession

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node


async def test_rebase_graph(session: AsyncSession, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(name="branch1", session=session)
    await branch1.rebase(session=session)

    # Query all cars in MAIN, AFTER the rebase
    cars = sorted(await NodeManager.query(schema="TestCar", session=session), key=lambda c: c.id)
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 5
    assert cars[0].nbr_seats.is_protected is False

    # Query all cars in BRANCH1, AFTER the REBASE
    cars = sorted(await NodeManager.query(schema="TestCar", branch=branch1, session=session), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 4
    assert cars[0].nbr_seats.is_protected is True
    assert cars[2].id == "c3"
    assert cars[2].name.value == "volt"


async def test_rebase_graph_delete(session: AsyncSession, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(name="branch1", session=session)

    persons = sorted(await NodeManager.query(schema="TestPerson", session=session), key=lambda p: p.id)
    assert len(persons) == 3

    p3 = await NodeManager.get_one(id="p3", branch=branch1, session=session)
    await p3.delete(session=session)

    await branch1.rebase(session=session)

    # Query all cars in BRANCH1, AFTER the REBASE
    persons = sorted(await NodeManager.query(schema="TestPerson", branch=branch1, session=session), key=lambda p: p.id)
    assert len(persons) == 2


async def test_merge_relationship_many(session: AsyncSession, default_branch: Branch, register_core_models_schema):
    blue = await Node.init(session=session, schema="BuiltinTag", branch=default_branch)
    await blue.new(session=session, name="Blue", description="The Blue tag")
    await blue.save(session=session)

    red = await Node.init(session=session, schema="BuiltinTag", branch=default_branch)
    await red.new(session=session, name="red", description="The red tag")
    await red.save(session=session)

    yellow = await Node.init(session=session, schema="BuiltinTag", branch=default_branch)
    await yellow.new(session=session, name="yellow", description="The yellow tag")
    await yellow.save(session=session)

    org1 = await Node.init(session=session, schema="CoreOrganization", branch=default_branch)
    await org1.new(session=session, name="org1", tags=[blue])
    await org1.save(session=session)

    branch1 = await create_branch(branch_name="branch1", session=session)

    # Update the relationships for ORG1 >> TAGS in MAIN
    org1_main = await NodeManager.get_one(id=org1.id, session=session)
    await org1_main.tags.update(data=[blue, yellow], session=session)
    await org1_main.save(session=session)

    # Update the relationships for ORG1 >> TAGS in BRANCH1
    org1_branch = await NodeManager.get_one(id=org1.id, branch=branch1, session=session)
    await org1_branch.tags.update(data=[blue, red], session=session)
    await org1_branch.save(session=session)

    await branch1.rebase(session=session)

    # All Relationship are in BRANCH1 after the REBASE
    org1_branch = await NodeManager.get_one(id=org1.id, branch=branch1, session=session)
    assert len(await org1_branch.tags.get(session=session)) == 3
