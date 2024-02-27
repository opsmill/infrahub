from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.attribute.optional import AttributeOptionalChecker, AttributeOptionalUpdateValidatorQuery
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase


async def test_query_optional_true(db: InfrahubDatabase, default_branch: Branch, person_john_main, person_jane_main):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(
        db=db,
        name="ALFRED",
        height=160,
    )
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.optional = True

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name")

    query = await AttributeOptionalUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0


async def test_query_optional_false(db: InfrahubDatabase, default_branch: Branch, person_john_main, person_jane_main):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="ALFRED")
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    height_attr = person_schema.get_attribute(name="height")
    height_attr.optional = False

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height")

    query = await AttributeOptionalUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert all_data_paths == [
        DataPath(
            branch=default_branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person.id,
            kind="TestPerson",
            field_name="height",
        )
    ]


async def test_query_optional_update_on_branch(
    db: InfrahubDatabase, branch: Branch, person_john_main, person_jane_main
):
    person_john_main.height.value = None
    await person_john_main.save(db=db)

    await branch.rebase(db=db)
    person_john = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    person_john.height.value = 168
    await person_john.save(db=db)
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="ALFRED")
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    height_attr = person_schema.get_attribute(name="height")
    height_attr.optional = False

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height")

    query = await AttributeOptionalUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert all_data_paths == [
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person.id,
            kind="TestPerson",
            field_name="height",
        )
    ]


async def test_query_optional_node_deleted_on_branch(
    db: InfrahubDatabase, branch: Branch, person_john_main, person_jane_main
):
    person_john_main.height.value = None
    await person_john_main.save(db=db)

    await branch.rebase(db=db)
    person_john = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
    await person_john.delete(db=db)
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="ALFRED")
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    height_attr = person_schema.get_attribute(name="height")
    height_attr.optional = False

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height")

    query = await AttributeOptionalUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert all_data_paths == [
        DataPath(
            branch=branch.name,
            path_type=PathType.ATTRIBUTE,
            node_id=person.id,
            kind="TestPerson",
            field_name="height",
        )
    ]


async def test_validator(db: InfrahubDatabase, branch: Branch, person_john_main, person_jane_main):
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="ALFRED")
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    height_attr = person_schema.get_attribute(name="height")
    height_attr.optional = False
    registry.schema.set(name="TestPerson", schema=person_schema, branch=branch.name)

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="attribute.optional.update",
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height"),
    )

    constraint_checker = AttributeOptionalChecker(db=db, branch=branch)
    grouped_data_paths = await constraint_checker.check(request)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_all_data_paths()
    assert len(data_paths) == 1
    assert data_paths[0].node_id == person.id
    assert data_paths[0].branch == branch.name
