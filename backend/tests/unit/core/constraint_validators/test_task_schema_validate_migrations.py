from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.database import InfrahubDatabase


async def test_schema_validate_migrations(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main,
    helper,
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name).duplicate()
    person_schema = schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.parameters.regex = r"^[A-Z]+$"
    schema.set(name="TestPerson", schema=person_schema)

    constraints = [
        SchemaUpdateConstraintInfo(
            constraint_name="attribute.regex.update",
            path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name"),
        )
    ]

    message = SchemaValidateMigrationData(branch=default_branch, schema_branch=schema, constraints=constraints)
    responses = await schema_validate_migrations(message=message)

    assert len(responses) == 1
    assert len(responses[0].violations) == 1
    assert "Attribute-level 'regex' constraint violation" in responses[0].violations[0].message
    assert f"name='{person_john_main.name.value}'" in responses[0].violations[0].message
