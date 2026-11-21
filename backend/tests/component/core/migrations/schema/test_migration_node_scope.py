"""A schema migration given a set of node IDs changes only the nodes of its kinds whose IDs are in the set.

Each case loads the data set, runs the migration on part of the nodes of a kind, checks the nodes it changed
against a literal set and the other branch against a read taken before the run, then runs the migration on
the remaining nodes and expects nothing left to change.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest
from prefect.utilities.annotations import quote

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, HashableModelState, InfrahubKind, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.migrations import MIGRATION_MAP
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
)
from infrahub.core.migrations.schema.node_attribute_add import (
    NodeAttributeAddMigration,
    NodeAttributeAddMigrationQuery01,
)
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration, NodeKindUpdateMigrationQuery01
from infrahub.core.migrations.schema.node_relationship_remove import (
    NodeRelationshipRemoveMigration,
    NodeRelationshipRemoveMigrationQuery,
)
from infrahub.core.migrations.schema.node_remove import (
    NodeRemoveMigration,
    NodeRemoveMigrationQueryIn,
    NodeRemoveMigrationQueryOut,
)
from infrahub.core.migrations.schema.node_uniqueness_constraints_update import NodeUniquenessConstraintsUpdateMigration
from infrahub.core.migrations.schema.tasks import schema_path_migrate
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.definitions.core.template import core_object_component_template
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from tests.component.core.migrations.schema.selection_dataset import (
    BEACON_KIND,
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
    changed_node_ids,
    get_branch,
    load_selection_dataset,
    population,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.migrations.query.selection import MigrationSelectionQuery
    from infrahub.core.migrations.shared import SchemaMigration
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

UNKNOWN_NODE_ID = "18a9c2e0-5b7d-4c1e-9f3a-000000000000"

PROFILE_WIDGET_KIND = f"Profile{WIDGET_KIND}"
TEMPLATE_WIDGET_KIND = f"Template{WIDGET_KIND}"
RENAMED_WIDGET_KIND = "SelxWidget"

# The changes are read on the beacon kind too, so a beacon in the set that the migration changes fails the check
CHECKED_KINDS = [*population(WIDGET_KIND), BEACON_KIND]
WIDGET_POPULATION = population(WIDGET_KIND)


@dataclass
class PreparedMigration:
    migration: SchemaMigration
    queries: list[type[MigrationSelectionQuery]]
    init_kwargs: dict[str, Any]
    run_through_execute: bool = False
    """True when the migration builds its query in `execute()`, so the test runs `execute()` instead of the queries."""


type MigrationBuilder = Callable[[InfrahubDatabase, Branch], PreparedMigration]


def _attribute_add(db: InfrahubDatabase, branch: Branch) -> PreparedMigration:
    size = AttributeSchema(name="size", kind="Text", optional=True, branch=BranchSupportType.AWARE)
    migration = build_attribute_add_migration(NodeAttributeAddMigration, branch, WIDGET_KIND, size)
    return PreparedMigration(
        migration=migration, queries=[NodeAttributeAddMigrationQuery01], init_kwargs={"migration": migration}
    )


def _attribute_remove(db: InfrahubDatabase, branch: Branch) -> PreparedMigration:
    migration = build_attribute_migration(NodeAttributeRemoveMigration, branch, WIDGET_KIND, "color")
    return PreparedMigration(
        migration=migration, queries=[NodeAttributeRemoveMigrationQuery01], init_kwargs={"migration": migration}
    )


def _attribute_rename(db: InfrahubDatabase, branch: Branch) -> PreparedMigration:
    migration = build_attribute_migration(AttributeNameUpdateMigration, branch, WIDGET_KIND, "color", name="colour")
    return PreparedMigration(
        migration=migration, queries=[AttributeNameUpdateMigrationQuery01], init_kwargs={"migration": migration}
    )


def _attribute_kind_update(db: InfrahubDatabase, branch: Branch) -> PreparedMigration:
    migration = build_attribute_migration(AttributeKindUpdateMigration, branch, WIDGET_KIND, "color", kind="TextArea")
    return PreparedMigration(
        migration=migration, queries=[AttributeKindUpdateMigrationQuery], init_kwargs={"migration": migration}
    )


def _node_remove(db: InfrahubDatabase, branch: Branch) -> PreparedMigration:
    migration = build_node_remove_migration(branch, WIDGET_KIND)
    return PreparedMigration(
        migration=migration,
        queries=[NodeRemoveMigrationQueryIn, NodeRemoveMigrationQueryOut],
        init_kwargs={"migration": migration},
    )


def _relationship_remove(db: InfrahubDatabase, branch: Branch) -> PreparedMigration:
    migration, query_params = build_relationship_remove_params(db, branch, WIDGET_KIND, "gadget")
    return PreparedMigration(
        migration=migration,
        queries=[NodeRelationshipRemoveMigrationQuery],
        init_kwargs={"migration": migration, "query_params": query_params},
        run_through_execute=True,
    )


def _node_kind_update(db: InfrahubDatabase, branch: Branch) -> PreparedMigration:
    migration = build_node_kind_update_migration(branch, WIDGET_KIND, namespace="Selx")
    return PreparedMigration(
        migration=migration, queries=[NodeKindUpdateMigrationQuery01], init_kwargs={"migration": migration}
    )


@dataclass
class ScopeCase:
    name: str
    branch_name: str
    migration_class: type[SchemaMigration]
    build: MigrationBuilder
    scope: set[str]
    """Names of data set nodes in the set, which also holds an ID of no node."""
    expected_in_scope: dict[str, set[str]]
    """Names of the nodes the run on the set changes, per kind."""
    remaining: set[str]
    expected_remaining: dict[str, set[str]]
    verified_kinds: list[str] = field(default_factory=lambda: list(WIDGET_POPULATION))
    present_before: set[str] | None = None
    """Names of the nodes of the set a read on the case's branch returns before the run."""
    present_after: set[str] | None = None


# w1, w2 and w3 are active on main and w4 is deleted; on the branch w1, w3, w5 and w6 are active and w2 is deleted
MAIN_SCOPE = {"w1", "w4", "pw1", "tw1", "b1"}
MAIN_REMAINING = {"w2", "w3"}
BRANCH_SCOPE = {"w1", "w2", "w5", "pw1", "tw1", "b1"}
BRANCH_REMAINING = {"w3", "w6"}

MAIN_IN_SCOPE = {WIDGET_KIND: {"w1"}, PROFILE_WIDGET_KIND: {"pw1"}, TEMPLATE_WIDGET_KIND: {"tw1"}}
MAIN_REMAINING_CHANGED = {WIDGET_KIND: {"w2", "w3"}}
BRANCH_IN_SCOPE = {WIDGET_KIND: {"w1", "w5"}, PROFILE_WIDGET_KIND: {"pw1"}, TEMPLATE_WIDGET_KIND: {"tw1"}}
BRANCH_REMAINING_CHANGED = {WIDGET_KIND: {"w3", "w6"}}


def _attribute_cases(label: str, migration_class: type[SchemaMigration], build: MigrationBuilder) -> list[ScopeCase]:
    return [
        ScopeCase(
            name=f"{label}-main",
            branch_name="main",
            migration_class=migration_class,
            build=build,
            scope=MAIN_SCOPE,
            expected_in_scope=MAIN_IN_SCOPE,
            remaining=MAIN_REMAINING,
            expected_remaining=MAIN_REMAINING_CHANGED,
        ),
        ScopeCase(
            name=f"{label}-{SELECTION_BRANCH_NAME}",
            branch_name=SELECTION_BRANCH_NAME,
            migration_class=migration_class,
            build=build,
            scope=BRANCH_SCOPE,
            expected_in_scope=BRANCH_IN_SCOPE,
            remaining=BRANCH_REMAINING,
            expected_remaining=BRANCH_REMAINING_CHANGED,
        ),
    ]


RENAMED_WIDGET_POPULATION = [RENAMED_WIDGET_KIND, f"Profile{RENAMED_WIDGET_KIND}", f"Template{RENAMED_WIDGET_KIND}"]

SCOPE_CASES: list[ScopeCase] = [
    *_attribute_cases("attribute-add", NodeAttributeAddMigration, _attribute_add),
    *_attribute_cases("attribute-remove", NodeAttributeRemoveMigration, _attribute_remove),
    *_attribute_cases("attribute-rename", AttributeNameUpdateMigration, _attribute_rename),
    *_attribute_cases("attribute-kind-update", AttributeKindUpdateMigration, _attribute_kind_update),
    ScopeCase(
        name="node-kind-update-main",
        branch_name="main",
        migration_class=NodeKindUpdateMigration,
        build=_node_kind_update,
        scope=MAIN_SCOPE,
        expected_in_scope=MAIN_IN_SCOPE,
        remaining=MAIN_REMAINING,
        expected_remaining=MAIN_REMAINING_CHANGED,
        verified_kinds=[*WIDGET_POPULATION, *RENAMED_WIDGET_POPULATION],
    ),
    ScopeCase(
        name=f"node-kind-update-{SELECTION_BRANCH_NAME}",
        branch_name=SELECTION_BRANCH_NAME,
        migration_class=NodeKindUpdateMigration,
        build=_node_kind_update,
        scope=BRANCH_SCOPE,
        expected_in_scope=BRANCH_IN_SCOPE,
        remaining=BRANCH_REMAINING,
        expected_remaining=BRANCH_REMAINING_CHANGED,
        verified_kinds=[*WIDGET_POPULATION, *RENAMED_WIDGET_POPULATION],
    ),
    # A node removal leaves the profile and template nodes of the kind in place
    ScopeCase(
        name="node-remove-main",
        branch_name="main",
        migration_class=NodeRemoveMigration,
        build=_node_remove,
        scope=MAIN_SCOPE,
        expected_in_scope={WIDGET_KIND: {"w1"}},
        remaining=MAIN_REMAINING,
        expected_remaining=MAIN_REMAINING_CHANGED,
        present_before={"w1", "pw1", "tw1", "b1"},
        present_after={"pw1", "tw1", "b1"},
    ),
    ScopeCase(
        name=f"node-remove-{SELECTION_BRANCH_NAME}",
        branch_name=SELECTION_BRANCH_NAME,
        migration_class=NodeRemoveMigration,
        build=_node_remove,
        scope=BRANCH_SCOPE,
        expected_in_scope={WIDGET_KIND: {"w1", "w5"}},
        remaining=BRANCH_REMAINING,
        expected_remaining=BRANCH_REMAINING_CHANGED,
        present_before={"w1", "w5", "pw1", "tw1", "b1"},
        present_after={"pw1", "tw1", "b1"},
    ),
    # g1 is the gadget of w1 and w2 on main; on the branch g1 is the gadget of w1 and g2 the gadget of w5 and w6
    ScopeCase(
        name="relationship-remove-main",
        branch_name="main",
        migration_class=NodeRelationshipRemoveMigration,
        build=_relationship_remove,
        scope=MAIN_SCOPE,
        expected_in_scope={WIDGET_KIND: {"w1"}},
        remaining=MAIN_REMAINING,
        expected_remaining={WIDGET_KIND: {"w2"}},
        verified_kinds=[*WIDGET_POPULATION, GADGET_KIND],
    ),
    ScopeCase(
        name=f"relationship-remove-{SELECTION_BRANCH_NAME}",
        branch_name=SELECTION_BRANCH_NAME,
        migration_class=NodeRelationshipRemoveMigration,
        build=_relationship_remove,
        scope=BRANCH_SCOPE,
        expected_in_scope={WIDGET_KIND: {"w1", "w5"}},
        remaining=BRANCH_REMAINING,
        expected_remaining={WIDGET_KIND: {"w6"}},
        verified_kinds=[*WIDGET_POPULATION, GADGET_KIND],
    ),
]


@pytest.fixture
async def selection_dataset(db: InfrahubDatabase, default_branch: Branch, node_group_schema: None) -> SelectionDataset:
    return await load_selection_dataset(db=db, default_branch=default_branch)


def _ids(nodes: dict[str, Node], names: set[str]) -> set[str]:
    return {nodes[name].id for name in names}


def _ids_per_kind(nodes: dict[str, Node], names_per_kind: dict[str, set[str]]) -> dict[str, set[str]]:
    return {kind: _ids(nodes, names) for kind, names in names_per_kind.items()}


async def _read_branch_aware_fields(
    db: InfrahubDatabase, branch: Branch, node_ids: set[str]
) -> dict[str, dict[str, Any]]:
    """Return the kind and the branch-aware attribute values and relationship peers of each node read on `branch`."""
    nodes = await NodeManager.get_many(db=db, ids=sorted(node_ids), branch=branch)
    fields: dict[str, dict[str, Any]] = {}
    for node_id, node in nodes.items():
        schema = node.get_schema()
        node_fields: dict[str, Any] = {"kind": node.get_kind()}
        for attribute in schema.attributes:
            if attribute.get_branch() == BranchSupportType.AWARE:
                node_fields[attribute.name] = node.get_attribute(name=attribute.name).value
        for relationship in schema.relationships:
            if relationship.branch == BranchSupportType.AWARE:
                peers = await node.get_relationship(name=relationship.name).get_peers(db=db)
                node_fields[relationship.name] = set(peers)
        fields[node_id] = node_fields
    return fields


async def _run_on_nodes(
    db: InfrahubDatabase,
    prepared: PreparedMigration,
    branch: Branch,
    node_ids: set[str],
    expected_ids: dict[str, set[str]],
) -> None:
    """Count and run the migration on `node_ids`, then check the nodes it changed against `expected_ids`."""
    expected_counts = {kind: len(ids) for kind, ids in expected_ids.items()}
    if not prepared.run_through_execute:
        await assert_count_matches_write(
            db=db,
            queries=prepared.queries,
            init_kwargs={**prepared.init_kwargs, "node_ids": sorted(node_ids)},
            branch=branch,
            expected=expected_counts,
            population=CHECKED_KINDS,
            expected_ids=expected_ids,
        )
        return

    at = Timestamp()
    count_query = await prepared.queries[-1].init(
        db=db, branch=branch, at=at, node_ids=sorted(node_ids), **prepared.init_kwargs
    )
    counted = await count_query.count_changes(db=db)
    result = await prepared.migration.execute(
        migration_input=MigrationInput(db=db, at=at, node_ids=frozenset(node_ids)), branch=branch
    )
    assert result.errors == []
    assert counted == expected_counts
    assert await changed_node_ids(db=db, kinds=CHECKED_KINDS, at=at) == expected_ids


@pytest.mark.parametrize("case", SCOPE_CASES, ids=lambda case: case.name)
async def test_migration_changes_only_the_nodes_in_the_set(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: ScopeCase
) -> None:
    nodes = selection_dataset.nodes
    branch = get_branch(selection_dataset, default_branch, case.branch_name)
    other_branch = default_branch if case.branch_name == SELECTION_BRANCH_NAME else selection_dataset.branch
    prepared = case.build(db, branch)
    assert type(prepared.migration) is case.migration_class

    scope_ids = _ids(nodes, case.scope) | {UNKNOWN_NODE_ID}
    expected_in_scope = _ids_per_kind(nodes, case.expected_in_scope)

    if case.present_before is not None:
        present = await NodeManager.get_many(db=db, ids=sorted(scope_ids), branch=branch)
        assert set(present) == _ids(nodes, case.present_before)
    other_branch_before = await _read_branch_aware_fields(db=db, branch=other_branch, node_ids=scope_ids)

    await _run_on_nodes(db=db, prepared=prepared, branch=branch, node_ids=scope_ids, expected_ids=expected_in_scope)

    if case.present_after is not None:
        present = await NodeManager.get_many(db=db, ids=sorted(scope_ids), branch=branch)
        assert set(present) == _ids(nodes, case.present_after)
    assert await _read_branch_aware_fields(db=db, branch=other_branch, node_ids=scope_ids) == other_branch_before

    await _run_on_nodes(
        db=db,
        prepared=prepared,
        branch=branch,
        node_ids=_ids(nodes, case.remaining),
        expected_ids=_ids_per_kind(nodes, case.expected_remaining),
    )

    unscoped = await prepared.queries[-1].init(db=db, branch=branch, **prepared.init_kwargs)
    assert await unscoped.count_changes(db=db) == {}

    await verify_graph(db=db, kinds=case.verified_kinds)


async def test_migration_task_changes_only_the_nodes_in_the_set(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset
) -> None:
    nodes = selection_dataset.nodes
    size = AttributeSchema(name="size", kind="Text", optional=True, branch=BranchSupportType.AWARE)
    migration = build_attribute_add_migration(NodeAttributeAddMigration, default_branch, WIDGET_KIND, size)

    at = Timestamp()
    result = await schema_path_migrate(
        branch=default_branch,
        migration_name="node.attribute.add",
        schema_path=migration.schema_path,
        database=db,
        at=at,
        new_node_schema=migration.new_node_schema,
        previous_node_schema=migration.previous_node_schema,
        node_ids=quote(sorted(_ids(nodes, {"w1", "w3"}))),
    )
    assert result.errors == []

    assert await changed_node_ids(db=db, kinds=CHECKED_KINDS, at=at) == {WIDGET_KIND: _ids(nodes, {"w1", "w3"})}

    await verify_graph(db=db, kinds=WIDGET_POPULATION)


async def test_migration_task_on_an_empty_set_changes_no_node(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset
) -> None:
    size = AttributeSchema(name="size", kind="Text", optional=True, branch=BranchSupportType.AWARE)
    migration = build_attribute_add_migration(NodeAttributeAddMigration, default_branch, WIDGET_KIND, size)

    at = Timestamp()
    result = await schema_path_migrate(
        branch=default_branch,
        migration_name="node.attribute.add",
        schema_path=migration.schema_path,
        database=db,
        at=at,
        new_node_schema=migration.new_node_schema,
        previous_node_schema=migration.previous_node_schema,
        node_ids=quote([]),
    )
    assert result.errors == []
    assert result.nbr_migrations_executed == 0

    assert await changed_node_ids(db=db, kinds=CHECKED_KINDS, at=at) == {}

    await verify_graph(db=db, kinds=WIDGET_POPULATION)


async def test_relationship_remove_on_an_empty_set_changes_no_node(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset
) -> None:
    migration, _ = build_relationship_remove_params(db, default_branch, WIDGET_KIND, "gadget")

    at = Timestamp()
    result = await migration.execute(
        migration_input=MigrationInput(db=db, at=at, node_ids=frozenset()), branch=default_branch
    )
    assert result.errors == []
    assert result.nbr_migrations_executed == 0

    assert await changed_node_ids(db=db, kinds=[*CHECKED_KINDS, GADGET_KIND], at=at) == {}

    await verify_graph(db=db, kinds=[*WIDGET_POPULATION, GADGET_KIND])


def test_every_migration_has_a_scope_case() -> None:
    covered = {case.migration_class for case in SCOPE_CASES} | {
        case.migration_class for case in PROFILE_AND_TEMPLATE_SCOPE_CASES
    }
    uncovered = sorted(
        migration_class.__name__
        for migration_class in {migration_class for migration_class in MIGRATION_MAP.values() if migration_class}
        if migration_class not in covered
    )
    assert uncovered == []


# ---------------------------------------------------------------------------
# Selections with their own shape
# ---------------------------------------------------------------------------


async def _active_attribute_values_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, node_ids: set[str], attribute_names: list[str]
) -> dict[str, dict[str, Any]]:
    """Return, per node, the value of each attribute of `attribute_names` the node holds on the default branch."""
    query = """
    MATCH (n:Node)-[r1:HAS_ATTRIBUTE]->(a:Attribute)-[r2:HAS_VALUE]->(av:AttributeValue)
    WHERE n.uuid IN $node_ids AND a.name IN $attribute_names
    AND all(r IN [r1, r2] WHERE r.branch = $branch AND r.status = "active" AND r.to IS NULL)
    RETURN n.uuid AS node_id, a.name AS name, av.value AS value
    """
    results = await db.execute_query(
        query=query,
        params={"node_ids": sorted(node_ids), "attribute_names": attribute_names, "branch": default_branch.name},
    )
    values: dict[str, dict[str, Any]] = {}
    for result in results:
        values.setdefault(result["node_id"], {})[result["name"]] = result["value"]
    return values


async def test_rename_leaves_the_nodes_outside_the_set_on_the_old_name(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset
) -> None:
    nodes = selection_dataset.nodes
    migration = build_attribute_migration(
        AttributeNameUpdateMigration, default_branch, WIDGET_KIND, "color", name="colour"
    )

    await assert_count_matches_write(
        db=db,
        queries=[AttributeNameUpdateMigrationQuery01],
        init_kwargs={"migration": migration, "node_ids": sorted(_ids(nodes, {"w1", "pw1", "tw1"}) | {UNKNOWN_NODE_ID})},
        branch=default_branch,
        expected={WIDGET_KIND: 1, PROFILE_WIDGET_KIND: 1, TEMPLATE_WIDGET_KIND: 1},
        population=CHECKED_KINDS,
        expected_ids=_ids_per_kind(
            nodes, {WIDGET_KIND: {"w1"}, PROFILE_WIDGET_KIND: {"pw1"}, TEMPLATE_WIDGET_KIND: {"tw1"}}
        ),
    )

    values = await _active_attribute_values_on_default_branch(
        db=db, default_branch=default_branch, node_ids=_ids(nodes, {"w1", "w2"}), attribute_names=["color", "colour"]
    )
    assert values == {nodes["w1"].id: {"colour": "red"}, nodes["w2"].id: {"color": "blue"}}

    await verify_graph(db=db, kinds=WIDGET_POPULATION)


@dataclass
class CarData:
    nodes: dict[str, Node]
    schema: SchemaBranch


CAR_KINDS = ["TestElectricCar", "TestGazCar", "TestPerson"]


@pytest.fixture
async def car_data(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics_unregistered: dict[str, Any]
) -> CarData:
    """Two electric cars, which redefine the color of the car generic, two gas cars and their owner."""
    for node_schema_dict in car_person_schema_generics_unregistered["nodes"]:
        if node_schema_dict["name"] == "ElectricCar":
            node_schema_dict["attributes"].append(
                {"name": "color", "kind": "Text", "default_value": "#555555", "max_length": 8}
            )
    schema = registry.schema.register_schema(
        schema=SchemaRoot(**car_person_schema_generics_unregistered), branch=default_branch.name
    )

    nodes: dict[str, Node] = {}
    nodes["owner"] = await Node.init(db=db, schema="TestPerson")
    await nodes["owner"].new(db=db, name="John", height=180)
    await nodes["owner"].save(db=db)
    for name in ("e1", "e2"):
        nodes[name] = await Node.init(db=db, schema="TestElectricCar")
        await nodes[name].new(db=db, name=name, nbr_seats=3, nbr_engine=4, owner=nodes["owner"], color="#aaabbbc")
        await nodes[name].save(db=db)
    for name in ("gz1", "gz2"):
        nodes[name] = await Node.init(db=db, schema="TestGazCar")
        await nodes[name].new(db=db, name=name, nbr_seats=4, mpg=25, owner=nodes["owner"])
        await nodes[name].save(db=db)
    return CarData(nodes=nodes, schema=schema)


def _remove_car_attribute(schema: SchemaBranch, attribute_name: str) -> NodeAttributeRemoveMigration:
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    car_schema.get_attribute(name=attribute_name).state = HashableModelState.ABSENT
    return NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name=attribute_name),
    )


async def test_attribute_remove_on_a_generic_skips_the_kind_that_redefines_it(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData
) -> None:
    nodes = car_data.nodes
    migration = _remove_car_attribute(schema=car_data.schema, attribute_name="color")

    await assert_count_matches_write(
        db=db,
        queries=[NodeAttributeRemoveMigrationQuery01],
        init_kwargs={"migration": migration, "node_ids": sorted(_ids(nodes, {"e1", "gz1", "owner"}))},
        branch=default_branch,
        expected={"TestGazCar": 1},
        population=CAR_KINDS,
        expected_ids={"TestGazCar": {nodes["gz1"].id}},
    )

    await verify_graph(db=db, kinds=CAR_KINDS)


async def test_attribute_remove_on_a_generic_changes_the_nodes_in_the_set_of_each_kind(
    db: InfrahubDatabase, default_branch: Branch, car_data: CarData
) -> None:
    nodes = car_data.nodes
    migration = _remove_car_attribute(schema=car_data.schema, attribute_name="nbr_seats")

    await assert_count_matches_write(
        db=db,
        queries=[NodeAttributeRemoveMigrationQuery01],
        init_kwargs={"migration": migration, "node_ids": sorted(_ids(nodes, {"e1", "gz1", "owner"}))},
        branch=default_branch,
        expected={"TestElectricCar": 1, "TestGazCar": 1},
        population=CAR_KINDS,
        expected_ids={"TestElectricCar": {nodes["e1"].id}, "TestGazCar": {nodes["gz1"].id}},
    )

    await verify_graph(db=db, kinds=CAR_KINDS)


def _inherit_generic(branch: Branch, generic: GenericSchema, kind: str) -> NodeKindUpdateMigration:
    """Register `generic`, add it to the parents of `kind` and return the migration of that change."""
    # Processing a schema with templates needs the component template generic
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_component_template]), branch=branch.name)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous_schema = schema_branch.get(name=kind, duplicate=True)

    registry.schema.set(name=generic.kind, schema=generic, branch=branch.name)
    node_schema = schema_branch.get_node(name=kind, duplicate=True)
    node_schema.inherit_from = [*node_schema.inherit_from, generic.kind]
    registry.schema.set(name=kind, schema=node_schema, branch=branch.name)
    registry.schema.process_schema_branch(name=branch.name)

    return NodeKindUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=registry.schema.get(name=kind, branch=branch.name, duplicate=False),
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name="inherit_from"),
    )


def _tagged_generic() -> GenericSchema:
    return GenericSchema(
        name="Tagged",
        namespace="Sel",
        branch=BranchSupportType.AWARE,
        attributes=[AttributeSchema(name="status", kind="Text", default_value="active", optional=True)],
    )


async def test_node_kind_update_adds_a_newly_inherited_attribute_to_the_nodes_in_the_set(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset
) -> None:
    nodes = selection_dataset.nodes
    migration = _inherit_generic(branch=default_branch, generic=_tagged_generic(), kind=WIDGET_KIND)

    at = Timestamp()
    scope_ids = _ids(nodes, {"w1", "pw1", "tw1", "b1"}) | {UNKNOWN_NODE_ID}
    result = await migration.execute(
        migration_input=MigrationInput(db=db, at=at, node_ids=frozenset(scope_ids)), branch=default_branch
    )
    assert result.errors == []

    assert await changed_node_ids(db=db, kinds=CHECKED_KINDS, at=at) == _ids_per_kind(
        nodes, {WIDGET_KIND: {"w1"}, PROFILE_WIDGET_KIND: {"pw1"}, TEMPLATE_WIDGET_KIND: {"tw1"}}
    )
    holders = await _active_attribute_values_on_default_branch(
        db=db,
        default_branch=default_branch,
        node_ids=_ids(nodes, {"w1", "w2", "w3", "pw1", "tw1"}),
        attribute_names=["status"],
    )
    assert set(holders) == _ids(nodes, {"w1", "pw1", "tw1"})

    await verify_graph(db=db, kinds=WIDGET_POPULATION)


async def test_node_kind_update_on_an_empty_set_changes_no_node(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset
) -> None:
    nodes = selection_dataset.nodes
    migration = _inherit_generic(branch=default_branch, generic=_tagged_generic(), kind=WIDGET_KIND)

    at = Timestamp()
    result = await migration.execute(
        migration_input=MigrationInput(db=db, at=at, node_ids=frozenset()), branch=default_branch
    )
    assert result.errors == []
    assert result.nbr_migrations_executed == 0

    assert await changed_node_ids(db=db, kinds=CHECKED_KINDS, at=at) == {}
    holders = await _active_attribute_values_on_default_branch(
        db=db,
        default_branch=default_branch,
        node_ids=_ids(nodes, {"w1", "w2", "w3", "pw1", "tw1"}),
        attribute_names=["status"],
    )
    assert holders == {}

    await verify_graph(db=db, kinds=WIDGET_POPULATION)


SERVER_KIND = "TestServer"
SERVER_NAME = AttributeSchema(name="name", kind="Text", unique=True, branch=BranchSupportType.AWARE)
RACK_UNIT = AttributeSchema(
    name="rack_unit",
    kind="NumberPool",
    optional=False,
    read_only=True,
    branch=BranchSupportType.AWARE,
    parameters=NumberPoolParameters(start_range=1, end_range=100),
)


@pytest.fixture
async def servers(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Node]:
    monkeypatch.setitem(registry.node, InfrahubKind.NUMBERPOOL, CoreNumberPool)
    server_schema = NodeSchema(
        name="Server", namespace="Test", branch=BranchSupportType.AWARE, attributes=[SERVER_NAME.model_copy()]
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[server_schema]), branch=default_branch.name)

    nodes: dict[str, Node] = {}
    for name in ("server-0", "server-1", "server-2"):
        nodes[name] = await Node.init(db=db, schema=SERVER_KIND, branch=default_branch)
        await nodes[name].new(db=db, name=name)
        await nodes[name].save(db=db)
    return nodes


def _add_rack_unit(default_branch: Branch) -> NodeAttributeAddMigration:
    """Register the server kind with a number pool attribute and return the migration that adds it."""
    previous_schema = registry.schema.get_node_schema(name=SERVER_KIND, branch=default_branch)
    new_schema = NodeSchema(
        name="Server",
        namespace="Test",
        branch=BranchSupportType.AWARE,
        attributes=[SERVER_NAME.model_copy(), RACK_UNIT.model_copy()],
    )
    migration = NodeAttributeAddMigration(
        previous_node_schema=previous_schema,
        new_node_schema=new_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=SERVER_KIND, field_name="rack_unit"),
    )
    registry.schema.set(name=SERVER_KIND, schema=new_schema, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)
    return migration


async def _rack_units(db: InfrahubDatabase, default_branch: Branch, servers: dict[str, Node]) -> dict[str, Any]:
    read = await NodeManager.get_many(db=db, ids=sorted(_ids(servers, set(servers))), branch=default_branch)
    return {
        str(node.get_attribute(name="name").value): node.get_attribute(name="rack_unit").value for node in read.values()
    }


async def test_number_pool_attribute_add_allocates_numbers_to_the_nodes_in_the_set(
    db: InfrahubDatabase, default_branch: Branch, servers: dict[str, Node]
) -> None:
    migration = _add_rack_unit(default_branch=default_branch)

    at = Timestamp()
    scope_ids = _ids(servers, {"server-0", "server-2"}) | {UNKNOWN_NODE_ID}
    result = await migration.execute(
        migration_input=MigrationInput(db=db, at=at, node_ids=frozenset(scope_ids)), branch=default_branch
    )
    assert result.errors == []

    assert await changed_node_ids(db=db, kinds=[SERVER_KIND], at=at) == {
        SERVER_KIND: _ids(servers, {"server-0", "server-2"})
    }
    rack_units = await _rack_units(db=db, default_branch=default_branch, servers=servers)
    assert len(rack_units) == 3
    assert rack_units["server-1"] is None
    assert sorted([rack_units["server-0"], rack_units["server-2"]]) == [1, 2]

    await verify_graph(db=db, kinds=[SERVER_KIND])


async def test_number_pool_attribute_add_on_an_empty_set_allocates_no_number(
    db: InfrahubDatabase, default_branch: Branch, servers: dict[str, Node]
) -> None:
    migration = _add_rack_unit(default_branch=default_branch)
    # Every server holds the attribute row before the run, so a number given to a server outside the set is saved
    add_rows = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await add_rows.execute(db=db)

    at = Timestamp()
    result = await migration.execute(
        migration_input=MigrationInput(db=db, at=at, node_ids=frozenset()), branch=default_branch
    )
    assert result.errors == []
    assert result.nbr_migrations_executed == 0

    assert await changed_node_ids(db=db, kinds=[SERVER_KIND], at=at) == {}
    assert await _rack_units(db=db, default_branch=default_branch, servers=servers) == {
        "server-0": None,
        "server-1": None,
        "server-2": None,
    }

    await verify_graph(db=db, kinds=[SERVER_KIND])


# ---------------------------------------------------------------------------
# Migrations that change only profile and template nodes
# ---------------------------------------------------------------------------


def _color_unique(branch: Branch) -> SchemaMigration:
    return build_attribute_migration(
        AttributeSupportsGeneratedSchemaMigration, branch, WIDGET_KIND, "color", unique=True
    )


def _color_in_uniqueness_constraints(branch: Branch) -> SchemaMigration:
    schema = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema.get(name=WIDGET_KIND)
    new_node = schema.duplicate().get(name=WIDGET_KIND)
    new_node.uniqueness_constraints = [*(new_node.uniqueness_constraints or []), ["color__value"]]
    return NodeUniquenessConstraintsUpdateMigration(
        previous_node_schema=previous_node,
        new_node_schema=new_node,
        schema_path=SchemaPath(
            path_type=SchemaPathType.NODE,
            schema_kind=WIDGET_KIND,
            field_name="uniqueness_constraints",
            property_name="uniqueness_constraints",
        ),
    )


@dataclass
class ProfileAndTemplateScopeCase:
    name: str
    migration_class: type[SchemaMigration]
    build: Callable[[Branch], SchemaMigration]
    scope: set[str]
    """Names of data set nodes in the first set, which also holds an ID of no node."""
    expected_in_scope: dict[str, set[str]]
    """Names of the nodes the run on the first set changes, per kind: each of them loses the color attribute."""
    remaining: set[str]
    expected_remaining: dict[str, set[str]]


PROFILE_AND_TEMPLATE_SCOPE_CASES = [
    ProfileAndTemplateScopeCase(
        name="attribute-unique-update",
        migration_class=AttributeSupportsGeneratedSchemaMigration,
        build=_color_unique,
        scope={"w1", "pw1", "b1"},
        expected_in_scope={PROFILE_WIDGET_KIND: {"pw1"}},
        remaining={"tw1"},
        expected_remaining={TEMPLATE_WIDGET_KIND: {"tw1"}},
    ),
    # The uniqueness constraints update changes profile nodes only.
    ProfileAndTemplateScopeCase(
        name="uniqueness-constraints-update",
        migration_class=NodeUniquenessConstraintsUpdateMigration,
        build=_color_in_uniqueness_constraints,
        scope={"w1", "tw1", "b1"},
        expected_in_scope={},
        remaining={"pw1"},
        expected_remaining={PROFILE_WIDGET_KIND: {"pw1"}},
    ),
]


async def _run_on_profile_and_template_nodes(
    db: InfrahubDatabase,
    default_branch: Branch,
    migration: SchemaMigration,
    profile_and_template_ids: set[str],
    node_ids: set[str],
    expected_ids: dict[str, set[str]],
) -> None:
    holders_before = await _active_attribute_values_on_default_branch(
        db=db, default_branch=default_branch, node_ids=profile_and_template_ids, attribute_names=["color"]
    )

    at = Timestamp()
    result = await migration.execute(
        migration_input=MigrationInput(db=db, at=at, node_ids=frozenset(node_ids)), branch=default_branch
    )
    assert result.errors == []

    assert await changed_node_ids(db=db, kinds=CHECKED_KINDS, at=at) == expected_ids
    changed = set().union(*expected_ids.values())
    holders_after = await _active_attribute_values_on_default_branch(
        db=db, default_branch=default_branch, node_ids=profile_and_template_ids, attribute_names=["color"]
    )
    assert holders_after == {node_id: values for node_id, values in holders_before.items() if node_id not in changed}


@pytest.mark.parametrize("case", PROFILE_AND_TEMPLATE_SCOPE_CASES, ids=lambda case: case.name)
async def test_profile_and_template_migration_changes_only_the_nodes_in_the_set(
    db: InfrahubDatabase, default_branch: Branch, selection_dataset: SelectionDataset, case: ProfileAndTemplateScopeCase
) -> None:
    nodes = selection_dataset.nodes
    migration = case.build(default_branch)
    assert type(migration) is case.migration_class
    profile_and_template_ids = _ids(nodes, {"pw1", "tw1"})

    await _run_on_profile_and_template_nodes(
        db=db,
        default_branch=default_branch,
        migration=migration,
        profile_and_template_ids=profile_and_template_ids,
        node_ids=_ids(nodes, case.scope) | {UNKNOWN_NODE_ID},
        expected_ids=_ids_per_kind(nodes, case.expected_in_scope),
    )
    await _run_on_profile_and_template_nodes(
        db=db,
        default_branch=default_branch,
        migration=migration,
        profile_and_template_ids=profile_and_template_ids,
        node_ids=_ids(nodes, case.remaining),
        expected_ids=_ids_per_kind(nodes, case.expected_remaining),
    )

    await verify_graph(db=db, kinds=WIDGET_POPULATION)
