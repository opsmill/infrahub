from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.changelog.diff import MigrationTracker
from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.constants import DiffAction, SchemaPathType
from infrahub.core.diff.model.path import EnrichedDiffAttribute
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.timestamp import Timestamp


def _rename_migration(*, kind: str, old_name: str, new_name: str) -> SchemaUpdateMigrationInfo:
    return SchemaUpdateMigrationInfo(
        migration_name="attribute.name.update",
        path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, property_name=old_name, field_name=new_name
        ),
    )


@dataclass
class AttributeNameCase:
    name: str
    migrations: list[SchemaUpdateMigrationInfo]
    node_kind: str
    attribute_name: str
    expected_name: str


ATTRIBUTE_NAME_CASES = [
    AttributeNameCase(
        name="renamed_attribute_resolves_to_new_name",
        migrations=[_rename_migration(kind="TestPerson", old_name="height", new_name="stature")],
        node_kind="TestPerson",
        attribute_name="height",
        expected_name="stature",
    ),
    AttributeNameCase(
        name="unlisted_kind_keeps_original_name",
        migrations=[_rename_migration(kind="TestPerson", old_name="height", new_name="stature")],
        node_kind="TestCar",
        attribute_name="height",
        expected_name="height",
    ),
    AttributeNameCase(
        name="unlisted_attribute_keeps_original_name",
        migrations=[_rename_migration(kind="TestPerson", old_name="height", new_name="stature")],
        node_kind="TestPerson",
        attribute_name="name",
        expected_name="name",
    ),
    AttributeNameCase(
        name="non_rename_migration_is_ignored",
        migrations=[
            SchemaUpdateMigrationInfo(
                migration_name="node.attribute.add",
                path=SchemaPath(
                    path_type=SchemaPathType.ATTRIBUTE,
                    schema_kind="TestPerson",
                    property_name="height",
                    field_name="stature",
                ),
            )
        ],
        node_kind="TestPerson",
        attribute_name="height",
        expected_name="height",
    ),
    AttributeNameCase(
        name="rename_without_new_name_keeps_original_name",
        migrations=[
            SchemaUpdateMigrationInfo(
                migration_name="attribute.name.update",
                path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", property_name="height"),
            )
        ],
        node_kind="TestPerson",
        attribute_name="height",
        expected_name="height",
    ),
]


@pytest.mark.parametrize("case", ATTRIBUTE_NAME_CASES, ids=lambda case: case.name)
def test_migration_tracker_resolves_attribute_name(case: AttributeNameCase) -> None:
    tracker = MigrationTracker(migrations=case.migrations)
    node = NodeChangelog(node_id="n1", node_kind=case.node_kind, display_label="label")
    attribute = EnrichedDiffAttribute(name=case.attribute_name, changed_at=Timestamp(), action=DiffAction.UPDATED)

    assert tracker.get_attribute_name(node=node, attribute=attribute) == case.expected_name


def test_migration_tracker_without_migrations_keeps_original_name() -> None:
    tracker = MigrationTracker()
    node = NodeChangelog(node_id="n1", node_kind="TestPerson", display_label="label")
    attribute = EnrichedDiffAttribute(name="height", changed_at=Timestamp(), action=DiffAction.UPDATED)

    assert tracker.get_attribute_name(node=node, attribute=attribute) == "height"
