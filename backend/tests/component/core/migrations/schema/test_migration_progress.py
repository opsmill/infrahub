from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, SchemaPathType
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData, SchemaMigrationPathResponseData
from infrahub.core.migrations.schema.tasks import _apply_migrations
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.timestamp import Timestamp
from tests.adapters.migration_recorder import (
    MIGRATION_ENDED,
    MIGRATION_STARTED,
    REGISTER,
    MigrationRecorderCall,
    RecordingMigrationRecorder,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_a_migration_reports_that_it_started_before_it_reports_its_result(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch, car_accord_main: Node
) -> None:
    previous_schema = registry.schema.get_schema_branch(name=default_branch.name)
    new_car_schema = previous_schema.get_node(name="TestCar", duplicate=False).duplicate()
    new_car_schema.attributes.append(AttributeSchema(name="smell", kind="Text", branch=BranchSupportType.AWARE))
    new_schema = previous_schema.duplicate()
    new_schema.set(name="TestCar", schema=new_car_schema)
    migration = SchemaUpdateMigrationInfo(
        path=SchemaPath(schema_kind="TestCar", path_type=SchemaPathType.ATTRIBUTE, field_name="smell"),
        migration_name="node.attribute.add",
    )
    recorder = RecordingMigrationRecorder()

    errors = await _apply_migrations(
        message=SchemaApplyMigrationData(
            branch=default_branch,
            previous_schema=previous_schema,
            new_schema=new_schema,
            migrations=[migration],
            at=Timestamp(),
        ),
        recorder=recorder,
        database=db,
        log=logging.getLogger(__name__),
    )

    assert errors == []
    assert recorder.calls == [
        MigrationRecorderCall(method=REGISTER, arguments={"migrations": [migration]}),
        MigrationRecorderCall(method=MIGRATION_STARTED, arguments={"position": 0}),
        MigrationRecorderCall(
            method=MIGRATION_ENDED,
            arguments={
                "position": 0,
                "result": SchemaMigrationPathResponseData(
                    migration_name="node.attribute.add",
                    schema_path=migration.path,
                    errors=[],
                    nbr_migrations_executed=1,
                ),
            },
        ),
    ]
