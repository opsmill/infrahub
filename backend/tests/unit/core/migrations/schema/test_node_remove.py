from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.node_remove import NodeRemoveMigration
from infrahub.core.path import SchemaPath
from tests.helpers.schema.manufacturer import MANUFACTURER
from tests.helpers.schema.person import PERSON
from tests.unit.core.migrations.schema.helpers import (
    CAR_KINDS,
    MANUFACTURER_KINDS,
    PERSON_KINDS,
    full_schema_branch,
    schema_branch,
)


def test_changed_kinds_of_a_node_removal_include_its_peers() -> None:
    changed_kinds = NodeRemoveMigration.get_changed_kinds(
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestingCar"),
        previous_schema=full_schema_branch(),
        new_schema=schema_branch(PERSON, MANUFACTURER),
    )

    assert changed_kinds == CAR_KINDS | PERSON_KINDS | MANUFACTURER_KINDS
