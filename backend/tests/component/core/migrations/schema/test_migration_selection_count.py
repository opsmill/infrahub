"""A schema migration query counts, before it runs, exactly the nodes of the migrated kinds that its write changes.

Every test counts with the query, runs it, compares the count with a value computed from the data set and
with the nodes that the write changed, then counts again and expects nothing left to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import HashableModelState, SchemaPathType
from infrahub.core.migrations.schema.attribute_supports_generated_schema import (
    AttributeSupportsGeneratedSchemaMigration,
    ProfilesAttributeRemoveMigrationQuery,
    TemplatesAttributeRemoveMigrationQuery,
)
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from tests.component.core.migrations.schema.selection_dataset import (
    BEACON_KIND,
    SELECTION_BRANCH_NAME,
    WIDGET_KIND,
    SelectionDataset,
    assert_count_matches_write,
    build_attribute_migration,
    get_branch,
    load_selection_dataset,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@dataclass
class CountCase:
    name: str
    branch_name: str
    expected: dict[str, int]


def _same_on_both_branches(expected: dict[str, int]) -> list[CountCase]:
    return [
        CountCase(name="main", branch_name="main", expected=expected),
        CountCase(name=SELECTION_BRANCH_NAME, branch_name=SELECTION_BRANCH_NAME, expected=expected),
    ]


@pytest.fixture
async def selection_dataset(db: InfrahubDatabase, default_branch: Branch, node_group_schema: None) -> SelectionDataset:
    return await load_selection_dataset(db=db, default_branch=default_branch)


# ---------------------------------------------------------------------------
# Attribute removal
# ---------------------------------------------------------------------------


WIDGET_AND_GENERATED_KINDS = {WIDGET_KIND: 3, f"Profile{WIDGET_KIND}": 1, f"Template{WIDGET_KIND}": 1}


@pytest.mark.parametrize("case", _same_on_both_branches(WIDGET_AND_GENERATED_KINDS), ids=lambda case: case.name)
async def test_attribute_remove_aware(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_attribute_migration(NodeAttributeRemoveMigration, branch, WIDGET_KIND, "color")
    await assert_count_matches_write(
        db=db,
        queries=[NodeAttributeRemoveMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


@dataclass
class GeneratedKindCase:
    name: str
    branch_name: str
    query: Any
    expected: dict[str, int]


GENERATED_KIND_CASES = [
    GeneratedKindCase(
        name=f"{label}-{branch_name}", branch_name=branch_name, query=query, expected={f"{prefix}{WIDGET_KIND}": 1}
    )
    for label, prefix, query in [
        ("profiles", "Profile", ProfilesAttributeRemoveMigrationQuery),
        ("templates", "Template", TemplatesAttributeRemoveMigrationQuery),
    ]
    for branch_name in ["main", SELECTION_BRANCH_NAME]
]


@pytest.mark.parametrize("case", GENERATED_KIND_CASES, ids=lambda case: case.name)
async def test_attribute_remove_generated_kinds(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: GeneratedKindCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_attribute_migration(AttributeSupportsGeneratedSchemaMigration, branch, WIDGET_KIND, "color")
    await assert_count_matches_write(
        db=db, queries=[case.query], init_kwargs={"migration": migration}, branch=branch, expected=case.expected
    )


@pytest.mark.parametrize("case", _same_on_both_branches(WIDGET_AND_GENERATED_KINDS), ids=lambda case: case.name)
async def test_attribute_remove_agnostic_attribute(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_attribute_migration(NodeAttributeRemoveMigration, branch, WIDGET_KIND, "serial")
    await assert_count_matches_write(
        db=db,
        queries=[NodeAttributeRemoveMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


@pytest.mark.parametrize("case", _same_on_both_branches({BEACON_KIND: 2}), ids=lambda case: case.name)
async def test_attribute_remove_agnostic_node(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_attribute_migration(NodeAttributeRemoveMigration, branch, BEACON_KIND, "serial")
    await assert_count_matches_write(
        db=db,
        queries=[NodeAttributeRemoveMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


async def test_attribute_remove_generic_with_override(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics_unregistered: dict[str, Any]
) -> None:
    for node_schema_dict in car_person_schema_generics_unregistered["nodes"]:
        if node_schema_dict["name"] == "ElectricCar":
            node_schema_dict["attributes"].append(
                {"name": "color", "kind": "Text", "default_value": "#555555", "max_length": 8}
            )
    schema = registry.schema.register_schema(
        schema=SchemaRoot(**car_person_schema_generics_unregistered), branch=default_branch.name
    )

    owner = await Node.init(db=db, schema="TestPerson")
    await owner.new(db=db, name="John", height=180)
    await owner.save(db=db)
    electric_car = await Node.init(db=db, schema="TestElectricCar")
    await electric_car.new(db=db, name="volt", nbr_seats=3, nbr_engine=4, owner=owner, color="#aaabbbc")
    await electric_car.save(db=db)
    gaz_car = await Node.init(db=db, schema="TestGazCar")
    await gaz_car.new(db=db, name="nolt", nbr_seats=4, mpg=25, owner=owner)
    await gaz_car.save(db=db)

    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    car_schema.get_attribute(name="color").state = HashableModelState.ABSENT
    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )

    await assert_count_matches_write(
        db=db,
        queries=[NodeAttributeRemoveMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=default_branch,
        expected={"TestGazCar": 1},
    )
