import pytest

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph import Migration018, Migration025
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def car_person_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_internal_models_schema,
    car_person_schema_unregistered: SchemaRoot,
) -> SchemaBranch:
    car_person_schema_unregistered.get("TestCar").uniqueness_constraints = [["color__value", "nbr_seats__value"]]
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


@pytest.fixture
async def person_main(db: InfrahubDatabase, default_branch: Branch, car_person_schema) -> Node:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)
    return person


@pytest.fixture
async def car_blue(db: InfrahubDatabase, default_branch: Branch, person_main: Node) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="car_blue", nbr_seats=5, is_electric=False, color="blue", owner=person_main.id)
    await car.save(db=db)
    return car


@pytest.fixture
async def car_red(db: InfrahubDatabase, default_branch: Branch, person_main: Node) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="car_red", nbr_seats=5, is_electric=False, color="red", owner=person_main.id)
    await car.save(db=db)
    return car


@pytest.fixture
async def car_invisible(db: InfrahubDatabase, default_branch: Branch, person_main: Node) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="car_invisible", nbr_seats=5, is_electric=False, color=None, owner=person_main.id)
    await car.save(db=db)
    car.color.value = None
    await car.save(db=db)
    return car


@pytest.mark.parametrize("migration", [Migration018(), Migration025()])
async def test_migration_018_success(
    db: InfrahubDatabase,
    default_branch,
    car_blue,
    car_red,
    car_invisible,
    migration,
) -> None:
    # check no validation errors for now
    async with db.start_session() as dbs:
        execution_result = await migration.execute(migration_input=MigrationInput(db=dbs))
        assert not execution_result.errors

        validation_result = await migration.validate_migration(db=dbs)
        assert not validation_result.errors


@pytest.mark.parametrize("migration", [Migration018(), Migration025()])
async def test_migration_018_fail(
    db: InfrahubDatabase,
    default_branch,
    car_blue,
    car_red,
    car_invisible,
    car_person_schema: SchemaBranch,
    migration,
) -> None:
    """
    Test migration correctly identifies nodes with NULL attribute values that violate uniqueness constraint
    """
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.load_schema_to_db(db=db, schema=schema_branch)
    car_red_update = await NodeManager.get_one(db=db, id=car_red.id)
    car_red_update.color.value = None
    await car_red_update.save(db=db)

    # check validation errors for two cars now
    async with db.start_session() as dbs:
        execution_result = await migration.execute(migration_input=MigrationInput(db=dbs))
        assert len(execution_result.errors) == 3
        for error_str in execution_result.errors[1:]:
            assert car_red.name.value in error_str or car_invisible.name.value in error_str
            assert "nbr_seats=5" in error_str
            assert "color=NULL" in error_str
