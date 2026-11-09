from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality, RelationshipDeleteBehavior
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.delete_validator import NodeDeleteValidator
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

BRANCH_NAME = "delete-check"
MANY = RelationshipCardinality.MANY
ONE = RelationshipCardinality.ONE


def _relationship(
    name: str,
    peer: str,
    identifier: str,
    cardinality: RelationshipCardinality,
    optional: bool,
    cascade: bool = False,
) -> RelationshipSchema:
    return RelationshipSchema(
        name=name,
        peer=peer,
        identifier=identifier,
        cardinality=cardinality,
        optional=optional,
        on_delete=RelationshipDeleteBehavior.CASCADE if cascade else None,
    )


def _node(name: str, relationships: list[RelationshipSchema]) -> NodeSchema:
    return NodeSchema(
        name=name,
        namespace="Test",
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        relationships=relationships,
    )


DELETE_CHECK_SCHEMA = SchemaRoot(
    nodes=[
        _node(
            "Region",
            [_relationship("sites", "TestSite", "region__site", MANY, optional=True, cascade=True)],
        ),
        _node(
            "Site",
            [
                _relationship("region", "TestRegion", "region__site", ONE, optional=False),
                _relationship("racks", "TestRack", "site__rack", MANY, optional=True, cascade=True),
            ],
        ),
        _node(
            "Rack",
            [
                _relationship("site", "TestSite", "site__rack", ONE, optional=False),
                _relationship("units", "TestUnit", "rack__unit", MANY, optional=True, cascade=True),
            ],
        ),
        _node("Unit", [_relationship("rack", "TestRack", "rack__unit", ONE, optional=False)]),
        _node("Label", [_relationship("unit", "TestUnit", "label__unit", ONE, optional=False)]),
        _node("Tag", [_relationship("units", "TestUnit", "tag__unit", MANY, optional=True)]),
        _node("CycleA", [_relationship("next", "TestCycleB", "cycle_a__b", ONE, optional=True, cascade=True)]),
        _node("CycleB", [_relationship("next", "TestCycleC", "cycle_b__c", ONE, optional=True, cascade=True)]),
        _node("CycleC", [_relationship("next", "TestCycleA", "cycle_c__a", ONE, optional=True, cascade=True)]),
        _node("Watcher", [_relationship("target", "TestCycleB", "watcher__cycle_b", ONE, optional=False)]),
    ]
)


@dataclass
class DeleteCheckData:
    ids: dict[str, str]
    names: dict[str, str]
    timestamps: dict[str, Timestamp] = field(default_factory=dict)


@pytest.fixture(scope="class")
async def delete_check_schema(
    db: InfrahubDatabase,
    default_branch_scope_class: Branch,
    register_core_models_schema_scope_class: SchemaBranch,
) -> None:
    registry.schema.register_schema(schema=DELETE_CHECK_SCHEMA, branch=default_branch_scope_class.name)
    registry.schema.process_schema_branch(name=default_branch_scope_class.name)


async def _create(db: InfrahubDatabase, branch: Branch, kind: str, name: str, **relationships: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, name=name, **relationships)
    await node.save(db=db)
    return node


@pytest.fixture(scope="class")
async def delete_check_data(
    db: InfrahubDatabase, default_branch_scope_class: Branch, delete_check_schema: None
) -> DeleteCheckData:
    """Builds the graph that every case reads.

    On main: region R1 holds sites S1 (racks K1 with units U1 and U2, K2 with unit U3) and S2 (rack K3
    with unit U4); label L1 requires U1; tag T1 points at U3 without cascading; region R2 holds site S3,
    rack K4 and unit U5; A1 -> B1 -> C1 -> A1 and A2 -> B2 -> C2 -> A2 are cascade cycles, and watcher W2
    requires B2. On the branch, after `before_branch`: U5 and L1 are deleted, rack K5 with unit U6 is
    added under S3. On main, after `before_main_change`: label L2 requiring U4 is added, then label L3
    requiring U2 is added and, after `before_main_removal`, deleted.
    """
    main = default_branch_scope_class
    nodes: dict[str, Node] = {}

    async def create(kind: str, name: str, branch: Branch = main, **relationships: Any) -> None:
        nodes[name] = await _create(db=db, branch=branch, kind=kind, name=name, **relationships)

    await create("TestRegion", "R1")
    await create("TestRegion", "R2")
    await create("TestSite", "S1", region=nodes["R1"])
    await create("TestSite", "S2", region=nodes["R1"])
    await create("TestSite", "S3", region=nodes["R2"])
    for rack, site in (("K1", "S1"), ("K2", "S1"), ("K3", "S2"), ("K4", "S3")):
        await create("TestRack", rack, site=nodes[site])
    for unit, rack in (("U1", "K1"), ("U2", "K1"), ("U3", "K2"), ("U4", "K3"), ("U5", "K4")):
        await create("TestUnit", unit, rack=nodes[rack])
    await create("TestLabel", "L1", unit=nodes["U1"])
    await create("TestTag", "T1", units=[nodes["U3"]])
    for suffix in ("1", "2"):
        await create("TestCycleC", f"C{suffix}")
        await create("TestCycleB", f"B{suffix}", next=nodes[f"C{suffix}"])
        await create("TestCycleA", f"A{suffix}", next=nodes[f"B{suffix}"])
        cycle_c = await NodeManager.get_one(db=db, id=nodes[f"C{suffix}"].id, branch=main)
        await cycle_c.get_relationship("next").update(db=db, data=nodes[f"A{suffix}"])
        await cycle_c.save(db=db)
    await create("TestWatcher", "W2", target=nodes["B2"])

    timestamps = {"before_branch": Timestamp()}

    branch = await create_branch(db=db, branch_name=BRANCH_NAME)
    for name in ("U5", "L1"):
        node_on_branch = await NodeManager.get_one(db=db, id=nodes[name].id, branch=branch)
        await node_on_branch.delete(db=db)
    await create("TestRack", "K5", branch=branch, site=nodes["S3"].id)
    await create("TestUnit", "U6", branch=branch, rack=nodes["K5"])

    timestamps["before_main_change"] = Timestamp()
    await create("TestLabel", "L2", unit=nodes["U4"])
    await create("TestLabel", "L3", unit=nodes["U2"])
    timestamps["before_main_removal"] = Timestamp()
    await nodes["L3"].delete(db=db)

    return DeleteCheckData(
        ids={name: node.id for name, node in nodes.items()},
        names={node.id: name for name, node in nodes.items()},
        timestamps=timestamps,
    )


@dataclass
class DependentNode:
    """A node outside the deletion that holds a mandatory relationship to a node inside it."""

    deleted_kind: str
    deleted: str
    relationship: str
    dependent_kind: str
    dependent: str


@dataclass
class DeleteCheckCase:
    name: str
    branch: str
    start: list[str]
    at: str | None = None
    expected_deleted: set[str] = field(default_factory=set)
    expected_dependents: list[DependentNode] = field(default_factory=list)


L1_REQUIRES_U1 = DependentNode(
    deleted_kind="TestUnit", deleted="U1", relationship="unit", dependent_kind="TestLabel", dependent="L1"
)
L2_REQUIRES_U4 = DependentNode(
    deleted_kind="TestUnit", deleted="U4", relationship="unit", dependent_kind="TestLabel", dependent="L2"
)
L3_REQUIRES_U2 = DependentNode(
    deleted_kind="TestUnit", deleted="U2", relationship="unit", dependent_kind="TestLabel", dependent="L3"
)
W2_REQUIRES_B2 = DependentNode(
    deleted_kind="TestCycleB", deleted="B2", relationship="target", dependent_kind="TestWatcher", dependent="W2"
)

DELETE_CHECK_CASES: list[DeleteCheckCase] = [
    DeleteCheckCase(
        name="cascade_three_levels_blocked_by_dependents_of_the_last_level",
        branch="main",
        start=["R1"],
        expected_dependents=[L1_REQUIRES_U1, L2_REQUIRES_U4],
    ),
    DeleteCheckCase(
        name="dependents_at_a_time_before_one_was_added",
        branch="main",
        start=["R1"],
        at="before_main_change",
        expected_dependents=[L1_REQUIRES_U1],
    ),
    DeleteCheckCase(
        name="dependents_at_a_time_before_one_was_deleted",
        branch="main",
        start=["R1"],
        at="before_main_removal",
        expected_dependents=[L1_REQUIRES_U1, L2_REQUIRES_U4, L3_REQUIRES_U2],
    ),
    DeleteCheckCase(
        name="cascade_three_levels_on_main",
        branch="main",
        start=["R2"],
        expected_deleted={"R2", "S3", "K4", "U5"},
    ),
    DeleteCheckCase(
        name="cascade_from_the_middle_level",
        branch="main",
        start=["K2"],
        expected_deleted={"K2", "U3"},
    ),
    DeleteCheckCase(
        name="dependent_that_is_deleted_with_the_node_does_not_block",
        branch="main",
        start=["K1", "L1"],
        expected_deleted={"K1", "U1", "U2", "L1"},
    ),
    DeleteCheckCase(
        name="cycle_of_cascades_from_first_node",
        branch="main",
        start=["A1"],
        expected_deleted={"A1", "B1", "C1"},
    ),
    DeleteCheckCase(
        name="cycle_of_cascades_from_last_node",
        branch="main",
        start=["C1"],
        expected_deleted={"A1", "B1", "C1"},
    ),
    DeleteCheckCase(
        name="cycle_of_cascades_blocked_by_dependent",
        branch="main",
        start=["A2"],
        expected_dependents=[W2_REQUIRES_B2],
    ),
    DeleteCheckCase(
        name="cycle_of_cascades_with_its_dependent",
        branch="main",
        start=["A2", "W2"],
        expected_deleted={"A2", "B2", "C2", "W2"},
    ),
    DeleteCheckCase(
        name="kind_without_cascade_or_dependent_relationships",
        branch="main",
        start=["T1"],
        expected_deleted={"T1"},
    ),
    DeleteCheckCase(
        name="kind_without_cascade_relationships_and_no_dependent",
        branch="main",
        start=["U3"],
        expected_deleted={"U3"},
    ),
    DeleteCheckCase(
        name="kind_without_cascade_relationships_blocked_by_dependent",
        branch="main",
        start=["U1"],
        expected_dependents=[L1_REQUIRES_U1],
    ),
    DeleteCheckCase(
        name="branch_ignores_dependent_deleted_on_branch_and_added_on_main_later",
        branch=BRANCH_NAME,
        start=["R1"],
        expected_deleted={"R1", "S1", "S2", "K1", "K2", "K3", "U1", "U2", "U3", "U4"},
    ),
    DeleteCheckCase(
        name="branch_at_a_time_before_the_dependent_was_deleted",
        branch=BRANCH_NAME,
        start=["R1"],
        at="before_branch",
        expected_dependents=[L1_REQUIRES_U1],
    ),
    DeleteCheckCase(
        name="branch_cascade_skips_node_deleted_and_includes_nodes_created_on_branch",
        branch=BRANCH_NAME,
        start=["R2"],
        expected_deleted={"R2", "S3", "K4", "K5", "U6"},
    ),
    DeleteCheckCase(
        name="branch_at_a_time_before_the_branch_changes",
        branch=BRANCH_NAME,
        start=["R2"],
        at="before_branch",
        expected_deleted={"R2", "S3", "K4", "U5"},
    ),
    DeleteCheckCase(
        name="branch_node_created_only_on_branch",
        branch=BRANCH_NAME,
        start=["K5"],
        expected_deleted={"K5", "U6"},
    ),
]


class TestNodeDeleteValidator:
    @pytest.mark.parametrize("case", DELETE_CHECK_CASES, ids=lambda case: case.name)
    async def test_nodes_to_delete_and_dependents(
        self,
        db: InfrahubDatabase,
        delete_check_data: DeleteCheckData,
        case: DeleteCheckCase,
    ) -> None:
        branch = await registry.get_branch(db=db, branch=case.branch)
        start_nodes = await NodeManager.get_many(
            db=db, ids=[delete_check_data.ids[name] for name in case.start], branch=branch
        )
        at = delete_check_data.timestamps[case.at] if case.at else None
        validator = NodeDeleteValidator(db=db, branch=branch)

        if not case.expected_dependents:
            ids_to_delete = await validator.get_ids_to_delete(nodes=list(start_nodes.values()), at=at)
            assert {delete_check_data.names[node_id] for node_id in ids_to_delete} == case.expected_deleted
            return

        with pytest.raises(ValidationError, match=r"^Cannot delete Test") as exc:
            await validator.get_ids_to_delete(nodes=list(start_nodes.values()), at=at)
        assert isinstance(exc.value.input_value, list)
        ids = delete_check_data.ids
        assert sorted(error.message for error in exc.value.input_value) == sorted(
            f"Cannot delete {dep.deleted_kind} '{ids[dep.deleted]}'. It is linked to mandatory relationship "
            f"{dep.relationship} on node {dep.dependent_kind} '{ids[dep.dependent]}' "
            f"at {dep.dependent_kind}.{dep.relationship}"
            for dep in case.expected_dependents
        )
