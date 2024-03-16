import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.attribute.length import AttributeLengthChecker, AttributeLengthUpdateValidatorQuery
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize("min_length,max_length", [(None, None), (None, 30), (1, None), (2, 10), (4, 4)])
async def test_query_length_success(
    db: InfrahubDatabase, default_branch: Branch, person_john_main, person_jane_main, min_length, max_length
):
    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.min_length = min_length
    name_attr.max_length = max_length

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")

    query = await AttributeLengthUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_length_too_short(
    db: InfrahubDatabase, default_branch: Branch, person_john_main, person_jane_main, person_albert_main
):
    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.min_length = 5
    name_attr.max_length = None

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")

    query = await AttributeLengthUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 2
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_john_main.id,
            kind="TestPerson",
            field_name="name",
        )
        in all_data_paths
    )
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_jane_main.id,
            kind="TestPerson",
            field_name="name",
        )
        in all_data_paths
    )


async def test_query_length_too_long(
    db: InfrahubDatabase, default_branch: Branch, person_john_main, person_jane_main, person_albert_main
):
    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.min_length = 2
    name_attr.max_length = 5

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")

    query = await AttributeLengthUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_albert_main.id,
            kind="TestPerson",
            field_name="name",
        )
        in all_data_paths
    )


async def test_query_update_on_branch(
    db: InfrahubDatabase, branch: Branch, default_branch: Branch, person_john_main, person_jane_main, person_albert_main
):
    person_john_main.name.value = "Jawnsy"
    await person_john_main.save(db=db)

    await branch.rebase(db=db)
    person_john = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    person_john.name.value = "Jon"
    await person_john.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.min_length = 2
    name_attr.max_length = 5

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")

    query = await AttributeLengthUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_albert_main.id,
            kind="TestPerson",
            field_name="name",
        )
        in all_data_paths
    )


async def test_query_delete_on_branch(
    db: InfrahubDatabase, branch: Branch, default_branch: Branch, person_john_main, person_jane_main, person_albert_main
):
    person_john_main.name.value = "Jawnsy-John-Johnny"
    await person_john_main.save(db=db)

    await branch.rebase(db=db)
    person_john = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    await person_john.delete(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.min_length = 2
    name_attr.max_length = 5

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")

    query = await AttributeLengthUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_albert_main.id,
            kind="TestPerson",
            field_name="name",
        )
        in all_data_paths
    )


async def test_validator(
    db: InfrahubDatabase, branch: Branch, default_branch: Branch, person_john_main, person_albert_main
):
    await branch.rebase(db=db)
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    name_attr = person_schema.get_attribute(name="name")
    name_attr.min_length = 3
    name_attr.max_length = 5
    registry.schema.set(name="TestPerson", schema=person_schema, branch=branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.min_length.update",
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name"),
    )

    constraint_checker = AttributeLengthChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 1
    assert (
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person_albert_main.id,
            kind="TestPerson",
            field_name="name",
        )
        in data_paths
    )
