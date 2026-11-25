import json

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath, SchemaPathType
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

APPLICATION_ID = "18a2cd5c-3f0b-4c41-9d3e-6a1d7c2b9e10"
USER_ID = "2b6f3e4a-91c7-4d1e-8a52-0c3d9f7e6b21"
MIGRATION_AT = "2026-03-04T05:06:07.123456Z"


def test_SchemaApplyMigrationData_serializer(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
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
        at=Timestamp(MIGRATION_AT),
        user_id=USER_ID,
        application_id=APPLICATION_ID,
    )

    data_dict = data.model_dump(mode="json")
    assert data_dict

    new_data = SchemaApplyMigrationData(**data_dict)
    assert new_data.model_dump(mode="json") == data_dict

    rebuilt = SchemaApplyMigrationData.model_validate(json.loads(data.model_dump_json()))
    assert rebuilt.application_id == APPLICATION_ID
    assert rebuilt.user_id == USER_ID
    assert rebuilt.at.to_string() == MIGRATION_AT
