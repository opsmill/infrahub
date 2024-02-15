from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathResourceType, PathType, SchemaPathType
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.relationship.optional import (
    RelationshipOptionalChecker,
    RelationshipOptionalUpdateValidatorQuery,
)
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.messages.schema_validator_path import SchemaValidatorPath


async def test_query(
    db: InfrahubDatabase, branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="Alfred", height=160)
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_rel = person_schema.get_relationship(name="cars")
    name_rel.optional = False

    node_schema = person_schema
    schema_path = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars")
    query = await RelationshipOptionalUpdateValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=schema_path
    )
    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_paths = grouped_paths.get_data_paths()
    assert all_paths == [
        DataPath(
            resource_type=PathResourceType.DATA,
            branch=branch.name,
            path_type=PathType.NODE,
            node_id=person.id,
            kind="TestPerson",
        )
    ]


async def test_validator(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Alfred", height=160)
    await person.save(db=db)

    person2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person2.new(db=db, name="Bob", height=150)
    await person2.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_rel = person_schema.get_relationship(name="cars")
    name_rel.optional = False

    message = SchemaValidatorPath(
        branch=default_branch,
        constraint_name="attribute.regex.update",
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars"),
    )

    constraint_checker = RelationshipOptionalChecker(db=db, branch=default_branch)
    grouped_data_paths = await constraint_checker.check(message)

    assert len(grouped_data_paths) == 1
    data_paths = grouped_data_paths[0].get_data_paths()
    assert len(data_paths) == 2
    assert {dp.node_id for dp in data_paths} == {person.id, person2.id}
