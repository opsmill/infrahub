from dataclasses import dataclass

import pytest

from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.node_relationship_remove import NodeRelationshipRemoveMigration
from infrahub.core.path import SchemaPath
from tests.unit.core.migrations.schema.helpers import (
    AUTO_KINDS,
    CAR_KINDS,
    PERSON_KINDS,
    full_schema_branch,
    renamed_car_schema_branches,
)


@dataclass(frozen=True, kw_only=True)
class RelationshipChangedKindsCase:
    name: str
    field_name: str
    expected: frozenset[str]


RELATIONSHIP_CHANGED_KINDS_CASES: list[RelationshipChangedKindsCase] = [
    RelationshipChangedKindsCase(
        name="relationship_removal_includes_peer", field_name="owner", expected=CAR_KINDS | PERSON_KINDS
    ),
    RelationshipChangedKindsCase(
        name="unknown_relationship_falls_back_to_node", field_name="missing", expected=CAR_KINDS
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in RELATIONSHIP_CHANGED_KINDS_CASES])
def test_changed_kinds_of_a_relationship_removal(case: RelationshipChangedKindsCase) -> None:
    changed_kinds = NodeRelationshipRemoveMigration.get_changed_kinds(
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestingCar", field_name=case.field_name
        ),
        previous_schema=full_schema_branch(),
        new_schema=full_schema_branch(),
    )

    assert changed_kinds == case.expected


def test_changed_kinds_of_a_relationship_removal_on_a_renamed_kind_include_the_peer() -> None:
    previous_schema, new_schema = renamed_car_schema_branches()

    changed_kinds = NodeRelationshipRemoveMigration.get_changed_kinds(
        schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestingAuto", field_name="owner"),
        previous_schema=previous_schema,
        new_schema=new_schema,
    )

    assert changed_kinds == AUTO_KINDS | CAR_KINDS | PERSON_KINDS
