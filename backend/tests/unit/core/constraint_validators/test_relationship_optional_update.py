from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.validators.relationship.optional import (
    RelationshipOptionalUpdateValidator,
    RelationshipOptionalUpdateValidatorQuery,
)
from infrahub.database import InfrahubDatabase


async def test_query(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main
):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Alfred", height=160)
    await person.save(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    name_rel = person_schema.get_relationship(name="cars")
    name_rel.optional = False

    validator = RelationshipOptionalUpdateValidator(
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars"),
    )
    query = await RelationshipOptionalUpdateValidatorQuery.init(db=db, branch=default_branch, validator=validator)
    await query.execute(db=db)
    paths = await query.get_paths()
    assert len(paths) == 1
    assert paths[0].node_id == person.id


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

    validator = RelationshipOptionalUpdateValidator(
        node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestPerson", field_name="cars"),
    )
    results = await validator.run_validate(db=db, branch=default_branch)

    assert len(results) == 2
    assert sorted([result.node_id for result in results]) == sorted([person.id, person2.id])
