from infrahub.core.branch.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def test_merge_graph(db: InfrahubDatabase, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(name="branch1", db=db)
    await branch1.merge_graph(db=db)

    # Query all cars in MAIN, AFTER the merge
    cars = sorted(await NodeManager.query(schema="TestCar", db=db), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 4
    assert cars[0].nbr_seats.is_protected is True
    assert cars[2].id == "c3"
    assert cars[2].name.value == "volt"

    # Query All cars in MAIN, BEFORE the merge
    cars = sorted(await NodeManager.query(schema="TestCar", at=base_dataset_02["time0"], db=db), key=lambda c: c.id)
    assert len(cars) == 2
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 5
    assert cars[0].nbr_seats.is_protected is False

    # Query all cars in BRANCH1, AFTER the merge
    cars = sorted(await NodeManager.query(schema="TestCar", branch=branch1, db=db), key=lambda c: c.id)
    assert len(cars) == 3
    assert cars[2].id == "c3"
    assert cars[2].name.value == "volt"

    # Query all cars in BRANCH1, BEFORE the merge
    cars = sorted(
        await NodeManager.query(schema="TestCar", branch=branch1, at=base_dataset_02["time0"], db=db),
        key=lambda c: c.id,
    )
    assert len(cars) == 3
    assert cars[0].id == "c1"
    assert cars[0].nbr_seats.value == 4

    # It should be possible to merge a graph even without changes
    await branch1.merge_graph(db=db)


async def test_merge_graph_delete(db: InfrahubDatabase, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(name="branch1", db=db)

    persons = sorted(await NodeManager.query(schema="TestPerson", db=db), key=lambda p: p.id)
    assert len(persons) == 3

    p3 = await NodeManager.get_one(id="p3", branch=branch1, db=db)
    await p3.delete(db=db)

    await branch1.merge_graph(db=db)

    # Query all cars in MAIN, AFTER the merge
    persons = sorted(await NodeManager.query(schema="TestPerson", db=db), key=lambda p: p.id)
    assert len(persons) == 2


async def test_merge_relationship_many(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, register_organization_schema
):
    blue = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await blue.new(db=db, name="Blue", description="The Blue tag")
    await blue.save(db=db)

    red = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await red.new(db=db, name="red", description="The red tag")
    await red.save(db=db)

    yellow = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await yellow.new(db=db, name="yellow", description="The yellow tag")
    await yellow.save(db=db)

    org1 = await Node.init(db=db, schema="CoreOrganization", branch=default_branch)
    await org1.new(db=db, name="org1", tags=[blue])
    await org1.save(db=db)

    branch1 = await create_branch(branch_name="branch1", db=db)

    org1_main = await NodeManager.get_one(id=org1.id, db=db)
    await org1_main.tags.update(data=[blue, yellow], db=db)
    await org1_main.save(db=db)

    org1_branch = await NodeManager.get_one(id=org1.id, branch=branch1, db=db)
    await org1_branch.tags.update(data=[blue, red], db=db)
    await org1_branch.save(db=db)

    await branch1.merge_graph(db=db)

    org1_main = await NodeManager.get_one(id=org1.id, db=db)
    assert len(await org1_main.tags.get(db=db)) == 3
