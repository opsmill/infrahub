from dataclasses import dataclass, field

import pytest

from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.schema.tasks import split_migrations_by_phase
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath

KIND_UPDATE_MIGRATION_NAMES = sorted(
    name for name, migration_class in MIGRATION_MAP.items() if migration_class is NodeKindUpdateMigration
)


def _migration_info(migration_name: str) -> SchemaUpdateMigrationInfo:
    return SchemaUpdateMigrationInfo(
        migration_name=migration_name,
        path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name"),
    )


@dataclass
class SplitMigrationsTestCase:
    name: str
    migration_names: list[str] = field(default_factory=list)
    expected_phase_1_names: list[str] = field(default_factory=list)
    expected_phase_2_names: list[str] = field(default_factory=list)


TEST_CASES = [
    SplitMigrationsTestCase(name="empty"),
    SplitMigrationsTestCase(
        name="only_kind_updates",
        migration_names=["node.inherit_from.update", "node.name.update", "node.namespace.update"],
        expected_phase_1_names=["node.inherit_from.update", "node.name.update", "node.namespace.update"],
    ),
    SplitMigrationsTestCase(
        name="only_other_migrations",
        migration_names=["node.attribute.add", "node.attribute.remove", "attribute.kind.update"],
        expected_phase_2_names=["node.attribute.add", "node.attribute.remove", "attribute.kind.update"],
    ),
    SplitMigrationsTestCase(
        name="mixed_preserves_relative_order",
        migration_names=[
            "node.attribute.add",
            "node.inherit_from.update",
            "attribute.kind.update",
            "node.name.update",
            "node.attribute.remove",
            "node.namespace.update",
        ],
        expected_phase_1_names=["node.inherit_from.update", "node.name.update", "node.namespace.update"],
        expected_phase_2_names=["node.attribute.add", "attribute.kind.update", "node.attribute.remove"],
    ),
    SplitMigrationsTestCase(
        name="duplicates_kept",
        migration_names=["node.inherit_from.update", "node.attribute.add", "node.inherit_from.update"],
        expected_phase_1_names=["node.inherit_from.update", "node.inherit_from.update"],
        expected_phase_2_names=["node.attribute.add"],
    ),
]


@pytest.mark.parametrize("test_case", TEST_CASES, ids=[test_case.name for test_case in TEST_CASES])
def test_split_migrations_by_phase(test_case: SplitMigrationsTestCase) -> None:
    migrations = [_migration_info(migration_name=name) for name in test_case.migration_names]

    phase_1, phase_2 = split_migrations_by_phase(migrations=migrations)

    assert [migration.migration_name for migration in phase_1] == test_case.expected_phase_1_names
    assert [migration.migration_name for migration in phase_2] == test_case.expected_phase_2_names


def test_split_covers_every_kind_update_backed_migration() -> None:
    migrations = [_migration_info(migration_name=name) for name in sorted(MIGRATION_MAP)]

    phase_1, phase_2 = split_migrations_by_phase(migrations=migrations)

    assert [migration.migration_name for migration in phase_1] == KIND_UPDATE_MIGRATION_NAMES
    assert sorted(migration.migration_name for migration in phase_2) == sorted(
        set(MIGRATION_MAP) - set(KIND_UPDATE_MIGRATION_NAMES)
    )
