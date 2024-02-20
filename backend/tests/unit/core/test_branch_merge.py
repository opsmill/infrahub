from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge import BranchMerger
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath, SchemaPathType
from infrahub.core.schema import AttributeSchema
from infrahub.database import InfrahubDatabase


async def test_validate_graph(db: InfrahubDatabase, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(name="branch1", db=db)

    merger = BranchMerger(db=db, source_branch=branch1)
    conflicts = await merger.validate_graph()

    assert not conflicts
    assert conflicts == []

    # Change the name of C1 in Branch1 to create a conflict
    c1 = await NodeManager.get_one(id="c1", branch=branch1, db=db)
    c1.name.value = "new name"
    await c1.save(db=db)

    merger = BranchMerger(db=db, source_branch=branch1)
    conflicts = await merger.validate_graph()

    assert conflicts
    assert conflicts[0].path == "data/c1/name/value"


async def test_validate_empty_branch(db: InfrahubDatabase, base_dataset_02, register_core_models_schema):
    branch2 = await create_branch(branch_name="branch2", db=db)

    merger = BranchMerger(db=db, source_branch=branch2)
    conflicts = await merger.validate_graph()

    assert not conflicts
    assert conflicts == []


async def test_merge_graph(db: InfrahubDatabase, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(name="branch1", db=db)

    merger = BranchMerger(db=db, source_branch=branch1)
    await merger.merge_graph()

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
    merger = BranchMerger(db=db, source_branch=branch1)
    await merger.merge_graph()


async def test_merge_graph_delete(db: InfrahubDatabase, base_dataset_02, register_core_models_schema):
    branch1 = await Branch.get_by_name(name="branch1", db=db)

    persons = sorted(await NodeManager.query(schema="TestPerson", db=db), key=lambda p: p.id)
    assert len(persons) == 3

    p3 = await NodeManager.get_one(id="p3", branch=branch1, db=db)
    await p3.delete(db=db)

    merger = BranchMerger(db=db, source_branch=branch1)
    await merger.merge_graph()

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

    merger = BranchMerger(db=db, source_branch=branch1)
    await merger.merge_graph()

    org1_main = await NodeManager.get_one(id=org1.id, db=db)
    assert len(await org1_main.tags.get(db=db)) == 3


async def test_merge_update_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main,
):
    schema_main = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.update_schema_branch(
        db=db, branch=default_branch, schema=schema_main, limit=["TestCar", "TestPerson"], update_db=True
    )

    branch2 = await create_branch(db=db, branch_name="branch2")

    # Update Schema in MAIN
    person_schema_main = schema_main.get(name="TestPerson")
    person_schema_main.attributes.pop(1)  # Remove height
    person_schema_main.attributes.append(AttributeSchema(name="color", kind="Text", optional=True))
    schema_main.set(name="TestPerson", schema=person_schema_main)
    schema_main.process()
    await registry.schema.update_schema_branch(
        db=db, branch=default_branch, schema=schema_main, limit=["TestCar", "TestPerson"], update_db=True
    )

    # Update Schema in BRANCH
    schema_branch = registry.schema.get_schema_branch(name=branch2.name)
    schema_branch.duplicate()
    car_schema_branch = schema_main.get(name="TestCar")
    car_schema_branch.attributes.pop(4)  # Remove transmission
    car_schema_branch.attributes.append(AttributeSchema(name="4motion", kind="Boolean", default_value=False))
    schema_branch.set(name="TestCar", schema=car_schema_branch)
    schema_branch.process()
    await registry.schema.update_schema_branch(
        db=db, branch=branch2, schema=schema_branch, limit=["TestCar", "TestPerson"], update_db=True
    )
    schema_branch = registry.schema.get_schema_branch(name=branch2.name)

    merger = BranchMerger(db=db, source_branch=branch2, destination_branch=default_branch)
    assert await merger.update_schema() is True
    assert sorted(merger.migrations, key=lambda x: x.path.get_path()) == sorted(
        [
            SchemaUpdateMigrationInfo(
                path=SchemaPath(
                    path_type=SchemaPathType.ATTRIBUTE,
                    schema_kind="TestCar",
                    schema_id=None,
                    field_name="4motion",
                    property_name=None,
                ),
                migration_name="node.attribute.add",
            ),
            SchemaUpdateMigrationInfo(
                path=SchemaPath(
                    path_type=SchemaPathType.ATTRIBUTE,
                    schema_kind="TestCar",
                    schema_id=None,
                    field_name="transmission",
                    property_name=None,
                ),
                migration_name="node.attribute.remove",
            ),
            SchemaUpdateMigrationInfo(
                path=SchemaPath(
                    path_type=SchemaPathType.ATTRIBUTE,
                    schema_kind="TestPerson",
                    schema_id=None,
                    field_name="color",
                    property_name=None,
                ),
                migration_name="node.attribute.add",
            ),
            SchemaUpdateMigrationInfo(
                path=SchemaPath(
                    path_type=SchemaPathType.ATTRIBUTE,
                    schema_kind="TestPerson",
                    schema_id=None,
                    field_name="height",
                    property_name=None,
                ),
                migration_name="node.attribute.remove",
            ),
        ],
        key=lambda x: x.path.get_path(),
    )
