from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.database import InfrahubDatabase
from infrahub.services import InfrahubServices, services
from infrahub.services.adapters.message_bus.local import BusSimulator
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution


async def test_schema_validate_migrations(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_test_fixture,
    car_accord_main: Node,
    car_volt_main: Node,
    person_john_main,
    helper,
):
    schema = registry.schema.get_schema_branch(name=default_branch.name).duplicate()
    person_schema = schema.get(name="TestPerson")
    name_attr = person_schema.get_attribute(name="name")
    name_attr.regex = r"^[A-Z]+$"
    schema.set(name="TestPerson", schema=person_schema)

    constraints = [
        SchemaUpdateConstraintInfo(
            constraint_name="attribute.regex.update",
            path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name"),
        )
    ]

    services.service = InfrahubServices(
        message_bus=BusSimulator(database=db), client=InfrahubClient(), workflow=WorkflowLocalExecution(), database=db
    )

    message = SchemaValidateMigrationData(branch=default_branch, schema_branch=schema, constraints=constraints)
    errors = await schema_validate_migrations(
        message=message,
    )

    assert len(errors) == 1
    assert "is not compatible with the constraint 'attribute.regex.update'" in errors[0]
