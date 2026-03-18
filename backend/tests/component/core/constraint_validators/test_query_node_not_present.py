from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.validators.query import NodeNotPresentValidatorQuery
from infrahub.database import InfrahubDatabase


async def test_query_node_present_with_data(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node, person_jane_main: Node
) -> None:
    person_schema = registry.schema.get(name="TestPerson")

    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")
    query = await NodeNotPresentValidatorQuery.init(
        db=db, branch=default_branch, node_schema=person_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2


async def test_query_node_present_with_data_rel(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node, person_jane_main: Node
) -> None:
    person_schema = registry.schema.get(name="TestPerson")

    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await NodeNotPresentValidatorQuery.init(
        db=db, branch=default_branch, node_schema=person_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2


async def test_query_node_present_no_data(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node, person_jane_main: Node
) -> None:
    car_schema = registry.schema.get(name="TestCar")

    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar")
    query = await NodeNotPresentValidatorQuery.init(
        db=db, branch=default_branch, node_schema=car_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0
