"""A schema migration query counts, before it runs, exactly the nodes of the migrated kinds that its write changes.

Every test counts with the query, runs it, compares the count with a value computed from the data set and
with the nodes that the write changed, then counts again and expects nothing left to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, HashableModelState, SchemaPathType
from infrahub.core.migrations.query.attribute_add import AttributeAddQuery
from infrahub.core.migrations.schema.attribute_kind_update import (
    AttributeKindUpdateMigration,
    AttributeKindUpdateMigrationQuery,
)
from infrahub.core.migrations.schema.attribute_name_update import (
    AttributeNameUpdateMigration,
    AttributeNameUpdateMigrationQuery01,
)
from infrahub.core.migrations.schema.attribute_supports_generated_schema import (
    AttributeSupportsGeneratedSchemaMigration,
    ProfilesAttributeRemoveMigrationQuery,
    TemplatesAttributeRemoveMigrationQuery,
)
from infrahub.core.migrations.schema.node_attribute_add import (
    NodeAttributeAddMigration,
    NodeAttributeAddMigrationQuery01,
)
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigrationQuery01
from infrahub.core.migrations.schema.node_relationship_remove import NodeRelationshipRemoveMigrationQuery
from infrahub.core.migrations.schema.node_remove import NodeRemoveMigrationQueryIn, NodeRemoveMigrationQueryOut
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, SchemaRoot
from tests.component.core.migrations.schema.selection_dataset import (
    BEACON_KIND,
    EMPTY_KIND,
    GADGET_KIND,
    SELECTION_BRANCH_NAME,
    WIDGET_KIND,
    SelectionDataset,
    assert_count_matches_write,
    build_attribute_add_migration,
    build_attribute_migration,
    build_node_kind_update_migration,
    build_node_remove_migration,
    build_relationship_remove_params,
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
    return _per_branch(on_main=expected, on_branch=expected)


def _per_branch(on_main: dict[str, int], on_branch: dict[str, int]) -> list[CountCase]:
    return [
        CountCase(name="main", branch_name="main", expected=on_main),
        CountCase(name=SELECTION_BRANCH_NAME, branch_name=SELECTION_BRANCH_NAME, expected=on_branch),
    ]


@pytest.fixture
async def selection_dataset(db: InfrahubDatabase, default_branch: Branch, node_group_schema: None) -> SelectionDataset:
    return await load_selection_dataset(db=db, default_branch=default_branch)


# ---------------------------------------------------------------------------
# Attribute removal
# ---------------------------------------------------------------------------


# w1, w2 and w3 are active on main; w1, w3, w5 and w6 on the branch, where w2 is deleted
WIDGET_AND_GENERATED_KINDS = _per_branch(
    on_main={WIDGET_KIND: 3, f"Profile{WIDGET_KIND}": 1, f"Template{WIDGET_KIND}": 1},
    on_branch={WIDGET_KIND: 4, f"Profile{WIDGET_KIND}": 1, f"Template{WIDGET_KIND}": 1},
)


@pytest.mark.parametrize("case", WIDGET_AND_GENERATED_KINDS, ids=lambda case: case.name)
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


@pytest.mark.parametrize("case", WIDGET_AND_GENERATED_KINDS, ids=lambda case: case.name)
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


# ---------------------------------------------------------------------------
# Attribute rename
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", WIDGET_AND_GENERATED_KINDS, ids=lambda case: case.name)
async def test_attribute_rename_aware(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_attribute_migration(AttributeNameUpdateMigration, branch, WIDGET_KIND, "color", name="colour")
    await assert_count_matches_write(
        db=db,
        queries=[AttributeNameUpdateMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


@pytest.mark.parametrize("case", _same_on_both_branches({BEACON_KIND: 2}), ids=lambda case: case.name)
async def test_attribute_rename_agnostic_node(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_attribute_migration(
        AttributeNameUpdateMigration, branch, BEACON_KIND, "serial", name="serial_number"
    )
    await assert_count_matches_write(
        db=db,
        queries=[AttributeNameUpdateMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
        check_remaining=case.branch_name == SELECTION_BRANCH_NAME,
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "on the default branch the rename closes only the edges the default branch owns and shadows none, "
        "so the old attribute of a branch-agnostic node stays active on the global branch"
    ),
)
async def test_attribute_rename_agnostic_node_leaves_nothing_on_main(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset
) -> None:
    migration = build_attribute_migration(
        AttributeNameUpdateMigration, default_branch, BEACON_KIND, "serial", name="serial_number"
    )
    await assert_count_matches_write(
        db=db,
        queries=[AttributeNameUpdateMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=default_branch,
        expected={BEACON_KIND: 2},
    )


# ---------------------------------------------------------------------------
# Attribute addition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", WIDGET_AND_GENERATED_KINDS, ids=lambda case: case.name)
async def test_attribute_add_aware(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    size = AttributeSchema(name="size", kind="Text", optional=True, branch=BranchSupportType.AWARE)
    migration = build_attribute_add_migration(NodeAttributeAddMigration, branch, WIDGET_KIND, size)
    await assert_count_matches_write(
        db=db,
        queries=[NodeAttributeAddMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


@pytest.mark.parametrize("case", _same_on_both_branches({BEACON_KIND: 2}), ids=lambda case: case.name)
async def test_attribute_add_local_on_agnostic_node(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    note = AttributeSchema(name="note", kind="Text", optional=True, branch=BranchSupportType.LOCAL)
    migration = build_attribute_add_migration(NodeAttributeAddMigration, branch, BEACON_KIND, note)
    await assert_count_matches_write(
        db=db,
        queries=[NodeAttributeAddMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


@pytest.mark.parametrize("case", _same_on_both_branches({WIDGET_KIND: 1}), ids=lambda case: case.name)
async def test_attribute_add_given_nodes(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    await assert_count_matches_write(
        db=db,
        queries=[AttributeAddQuery],
        init_kwargs={
            "node_kinds": [WIDGET_KIND],
            "attribute_name": "size",
            "attribute_kind": "Text",
            "branch_support": BranchSupportType.AWARE.value,
            "uuids": [selection_dataset.nodes["w1"].id],
        },
        branch=branch,
        expected=case.expected,
    )


# ---------------------------------------------------------------------------
# Node kind update
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", WIDGET_AND_GENERATED_KINDS, ids=lambda case: case.name)
async def test_node_kind_update_aware(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_node_kind_update_migration(branch, WIDGET_KIND, namespace="Selx")
    await assert_count_matches_write(
        db=db,
        queries=[NodeKindUpdateMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


@pytest.mark.parametrize("case", _same_on_both_branches({BEACON_KIND: 2}), ids=lambda case: case.name)
async def test_node_kind_update_agnostic_node(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_node_kind_update_migration(branch, BEACON_KIND, name="Lighthouse")
    await assert_count_matches_write(
        db=db,
        queries=[NodeKindUpdateMigrationQuery01],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


# ---------------------------------------------------------------------------
# Attribute kind update
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", WIDGET_AND_GENERATED_KINDS, ids=lambda case: case.name)
async def test_attribute_kind_update_to_large(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_attribute_migration(AttributeKindUpdateMigration, branch, WIDGET_KIND, "color", kind="TextArea")
    await assert_count_matches_write(
        db=db,
        queries=[AttributeKindUpdateMigrationQuery],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


@pytest.mark.parametrize("case", _same_on_both_branches({BEACON_KIND: 2}), ids=lambda case: case.name)
async def test_attribute_kind_update_agnostic_node(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_attribute_migration(AttributeKindUpdateMigration, branch, BEACON_KIND, "serial", kind="TextArea")
    await assert_count_matches_write(
        db=db,
        queries=[AttributeKindUpdateMigrationQuery],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


# ---------------------------------------------------------------------------
# Node removal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case", _per_branch(on_main={WIDGET_KIND: 3}, on_branch={WIDGET_KIND: 4}), ids=lambda case: case.name
)
async def test_node_remove_aware(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration = build_node_remove_migration(branch, WIDGET_KIND)
    inbound = await NodeRemoveMigrationQueryIn.init(db=db, branch=branch, migration=migration)
    assert await inbound.count_changes(db=db) == case.expected

    await assert_count_matches_write(
        db=db,
        queries=[NodeRemoveMigrationQueryIn, NodeRemoveMigrationQueryOut],
        init_kwargs={"migration": migration},
        branch=branch,
        expected=case.expected,
    )


@pytest.mark.parametrize("case", _same_on_both_branches({BEACON_KIND: 2}), ids=lambda case: case.name)
async def test_node_remove_agnostic_node(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: CountCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    await assert_count_matches_write(
        db=db,
        queries=[NodeRemoveMigrationQueryIn, NodeRemoveMigrationQueryOut],
        init_kwargs={"migration": build_node_remove_migration(branch, BEACON_KIND)},
        branch=branch,
        expected=case.expected,
    )


async def test_node_remove_empty_kind(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset
) -> None:
    await assert_count_matches_write(
        db=db,
        queries=[NodeRemoveMigrationQueryIn, NodeRemoveMigrationQueryOut],
        init_kwargs={"migration": build_node_remove_migration(default_branch, EMPTY_KIND)},
        branch=default_branch,
        expected={},
    )


# ---------------------------------------------------------------------------
# Relationship removal
# ---------------------------------------------------------------------------


@dataclass
class RelationshipCase:
    name: str
    branch_name: str
    node_kind: str
    relationship_name: str
    expected: dict[str, int]


# g1 is the peer of w1 and w2 on main; g2 is the peer of w5 and w6 on the branch, where w2 is deleted
RELATIONSHIP_CASES = [
    RelationshipCase(
        name="aware-main",
        branch_name="main",
        node_kind=WIDGET_KIND,
        relationship_name="gadget",
        expected={WIDGET_KIND: 2},
    ),
    RelationshipCase(
        name="aware-branch",
        branch_name=SELECTION_BRANCH_NAME,
        node_kind=WIDGET_KIND,
        relationship_name="gadget",
        expected={WIDGET_KIND: 3},
    ),
    RelationshipCase(
        name="agnostic-main",
        branch_name="main",
        node_kind=WIDGET_KIND,
        relationship_name="partner",
        expected={WIDGET_KIND: 1},
    ),
    RelationshipCase(
        name="agnostic-branch",
        branch_name=SELECTION_BRANCH_NAME,
        node_kind=WIDGET_KIND,
        relationship_name="partner",
        expected={WIDGET_KIND: 1},
    ),
    RelationshipCase(
        name="many-peers-main",
        branch_name="main",
        node_kind=GADGET_KIND,
        relationship_name="widgets",
        expected={GADGET_KIND: 1},
    ),
    RelationshipCase(
        name="many-peers-branch",
        branch_name=SELECTION_BRANCH_NAME,
        node_kind=GADGET_KIND,
        relationship_name="widgets",
        expected={GADGET_KIND: 2},
    ),
]


@pytest.mark.parametrize("case", RELATIONSHIP_CASES, ids=lambda case: case.name)
async def test_relationship_remove(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: RelationshipCase
) -> None:
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    migration, query_params = build_relationship_remove_params(db, branch, case.node_kind, case.relationship_name)
    await assert_count_matches_write(
        db=db,
        queries=[NodeRelationshipRemoveMigrationQuery],
        init_kwargs={"migration": migration, "query_params": query_params},
        branch=branch,
        expected=case.expected,
    )
