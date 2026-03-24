from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath, SchemaPathType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


def test_SchemaApplyMigrationData_serializer(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, car_person_schema
) -> None:
    schema_main = registry.schema.get_schema_branch(name=default_branch.name)

    data = SchemaApplyMigrationData(
        branch=default_branch,
        new_schema=schema_main,
        previous_schema=schema_main,
        migrations=[
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
        ],
        at=Timestamp(),
    )

    data_dict = data.model_dump(mode="json")
    assert data_dict

    new_data = SchemaApplyMigrationData(**data_dict)
    assert new_data.model_dump(mode="json") == data_dict
