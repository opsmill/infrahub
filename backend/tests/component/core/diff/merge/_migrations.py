"""Schema migration helpers shared by the source/target branch migration tests.

Both source- and target-branch migration scenarios perform the same TestCar ->
Test2NewCar rename on a specific branch's schema and execute the
``NodeKindUpdateMigration``. The only real difference is *which* branch gets
the new schema and whether the original ``TestCar`` schema is deleted (target
branch fully rotates it; source branch keeps it because the main branch hasn't
migrated yet).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.path import SchemaPath
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def migrate_testcar_to_test2newcar(
    *,
    db: InfrahubDatabase,
    target_branch: Branch,
    delete_old_schema: bool,
) -> Timestamp:
    """Rename ``TestCar`` to ``Test2NewCar`` on ``target_branch`` and run the node-kind migration.

    Also updates peer references on ``TestPerson`` (``cars``, ``cars_driven``) and
    ``TestManufacturer`` (``cars``).

    When ``delete_old_schema=True`` the ``TestCar`` schema is removed from the
    branch (used by the target-branch scenario where main fully rotates). When
    ``False`` the old schema remains registered (used by the source-branch
    scenario where the branch migrates but main still sees ``TestCar``).
    """
    schema = registry.schema.get_schema_branch(name=target_branch.name)

    original_car_schema = schema.get(name="TestCar", duplicate=True)
    new_car_schema = schema.get(name="TestCar", duplicate=True)
    new_car_schema.name = "NewCar"
    new_car_schema.namespace = "Test2"
    assert new_car_schema.kind == "Test2NewCar"
    schema.set(name="Test2NewCar", schema=new_car_schema)

    person_schema = schema.get(name="TestPerson", duplicate=True)
    person_schema.get_relationship("cars").peer = "Test2NewCar"
    person_schema.get_relationship("cars_driven").peer = "Test2NewCar"
    schema.set(name="TestPerson", schema=person_schema)

    manufacturer_schema = schema.get(name="TestManufacturer", duplicate=True)
    manufacturer_schema.get_relationship("cars").peer = "Test2NewCar"
    schema.set(name="TestManufacturer", schema=manufacturer_schema)

    if delete_old_schema:
        schema.delete(name="TestCar")

    schema.process()
    await registry.schema.update_schema_branch(
        db=db,
        branch=target_branch,
        schema=schema,
        limit=["TestCar", "Test2NewCar", "TestPerson", "TestManufacturer"],
        update_db=True,
    )

    migration = NodeKindUpdateMigration(
        previous_node_schema=original_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    migration_at = Timestamp()
    result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_at, user_id="migration-user"),
        branch=target_branch,
    )
    assert not result.errors
    return migration_at
