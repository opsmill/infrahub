from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.path import SchemaPath
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.database import InfrahubDatabase


async def test_schema_validate_migrations(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema,
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)

    constraints = [
        SchemaUpdateConstraintInfo(
            constraint_name="attribute.regex.update",
            path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="name"),
        )
    ]

    migration_data = SchemaValidateMigrationData(branch=default_branch, schema_branch=schema, constraints=constraints)

    # Validate that we can serialize and deserialize the SchemaValidateMigrationData properly
    # This is important because the message is used in Prefect
    data = migration_data.model_dump(mode="json")
    assert data

    new_migration_data = SchemaValidateMigrationData(**data)
    assert new_migration_data.model_dump(mode="json") == data
