import sys
from typing import Any
from unittest.mock import AsyncMock

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.protocols import CoreNumberPool as CoreNumberPoolProtocol
from infrahub.core.query.node import NodeCreateAllQuery
from infrahub.core.query.resource_manager import (
    NumberPoolChangeReserved,
    NumberPoolGetAllocated,
    NumberPoolGetReserved,
    NumberPoolGetUsed,
    NumberPoolSetReserved,
    PoolRecordProvenance,
)
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.db_query_counter import CountingInfrahubDatabase

REQUEST = NodeSchema(
    name="Request",
    namespace="Test",
    label="Request",
    attributes=[
        AttributeSchema(name="title", kind="Text", unique=False, optional=False),
        AttributeSchema(
            name="number",
            kind="NumberPool",
            optional=False,
            read_only=True,
            unique=True,
            parameters=NumberPoolParameters(start_range=1, end_range=sys.maxsize),
        ),
    ],
)

INCIDENT = NodeSchema(
    name="Incident",
    namespace="Test",
    label="Incident",
    attributes=[
        AttributeSchema(name="title", kind="Text", unique=False, optional=False),
        AttributeSchema(
            name="number",
            kind="NumberPool",
            optional=False,
            read_only=True,
            unique=True,
            parameters=NumberPoolParameters(start_range=1, end_range=sys.maxsize),
        ),
    ],
)


@pytest.fixture
async def register_test_schema(default_branch: Branch, register_core_models_schema: SchemaBranch) -> SchemaBranch:
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

    schema = SchemaRoot(
        version="1.0",
        nodes=[REQUEST, INCIDENT],
    )
    schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()

    return schema_branch


@pytest.fixture
async def run_number_pool_validation(db: InfrahubDatabase) -> None:
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    snps = SchemaNumberPoolSynchronizer(
        db=db,
        schema_manager=registry.schema,
        upserter=upserter,
        range_store_factory=NumberPoolRepository,
    )
    await snps.run()


async def create_objects(db: InfrahubDatabase, schema: NodeSchema, branch: str, start: int, end: int) -> list[Node]:
    """Helper function to create incidents."""
    nodes = []
    for idx in range(start, end + 1):
        incident = await Node.init(db=db, schema=schema, branch=branch)
        await incident.new(db=db, title=f"{schema.name} #{idx}")
        await incident.save(db=db)
        nodes.append(incident)
    return nodes


def whole_pool_ranges(pool: CoreNumberPoolProtocol) -> list[list[int]]:
    return [[pool.get_attribute("start_range").value, pool.get_attribute("end_range").value]]


async def get_used_numbers_in_pool(db: InfrahubDatabase, pool: CoreNumberPoolProtocol, branch: Branch) -> list[int]:
    """Helper function to get used numbers in a pool."""
    query = await NumberPoolGetUsed.init(
        db=db, branch=branch, pool=pool, ranges=whole_pool_ranges(pool), branch_agnostic=True
    )
    await query.execute(db=db)
    return sorted([result.value for result in query.iter_results()])


async def get_reservations(db: InfrahubDatabase, pool: CoreNumberPoolProtocol, branch: Branch) -> dict[str, int]:
    query1 = await NumberPoolGetReserved.init(db=db, pool_id=pool.get_id(), branch=branch)
    await query1.execute(db=db)
    return {item.identifier: item.value for item in query1.get_data()}


class TestNumberPoolGetUsed:
    async def test_NumberPoolGetUsed(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        request_schema = registry.schema.get_node_schema(name=REQUEST.kind, branch=default_branch)

        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        await create_objects(db=db, schema=request_schema, branch=default_branch.name, start=1, end=6)

        # Identify the NumberPool for each model
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        assert len(pools) == 2
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        # Validate that the incident NumberPool has 3 used values
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 2, 3]

        # Create a new branch and add more incidents
        # Ensure the query returns all used numbers across branches
        branch2 = await create_branch(db=db, branch_name="branch2")
        await create_objects(db=db, schema=incident_schema, branch=branch2.name, start=4, end=7)

        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 2, 3, 4, 5, 6, 7]

        # Delete the branch and validate that the numbers allocated previously are available
        await BranchDataDeleter(db=db, batch_size=5).delete(branch=branch2)
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 2, 3]

        # Create a new branch and add more incidents
        # to ensure the query returns all used numbers across branches
        branch3 = await create_branch(db=db, branch_name="branch3")
        await create_objects(db=db, schema=incident_schema, branch=branch3.name, start=11, end=13)
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 2, 3, 4, 5, 6]

        # Delete the branch and validate that the numbers allocated previously are available
        await BranchDataDeleter(db=db, batch_size=5).delete(branch=branch3)
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 2, 3]

        # Delete nodes in main and ensure the numbers are reallocated
        await incidents[1].delete(db=db)
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [1, 3]


class TestNumberPoolGetAllocated:
    async def test_NumberPoolGetAllocated_returns_identifier(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """Test that NumberPoolGetAllocated returns the identifier (node UUID) from the IS_RESERVED relationship."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        query = await NumberPoolGetAllocated.init(
            db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True
        )

        # Act
        await query.execute(db=db)
        results = query.get_data()

        assert len(results) == 3
        # Build a lookup by allocated value
        results_by_value = {r.value: r for r in results}

        # Each allocated result should have the identifier set to the node UUID
        for idx, incident in enumerate(incidents, start=1):
            result = results_by_value[idx]
            assert result.identifier == incident.get_id()

    async def test_NumberPoolGetAllocated_excludes_deleted(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """When a node is deleted on main branch which is the only branch having this allocated value,.

        NumberPoolGetAllocated should not return it.

        """
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        incident2 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=default_branch)
        await incident2.delete(db=db)

        query = await NumberPoolGetAllocated.init(
            db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True
        )
        await query.execute(db=db)
        results = query.get_data()

        allocated_values = sorted([r.value for r in results])
        assert allocated_values == [1, 3], (
            f"Expected deleted allocation (value=2) to be excluded on branch, got {allocated_values}"
        )

    async def test_NumberPoolGetAllocated_includes_allocation_active_on_other_branch(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """When a node created on main is deleted on a branch, NumberPoolGetAllocated still returns it."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        # Create a branch and delete incident #2 on that branch
        branch2 = await create_branch(db=db, branch_name="branch2")
        incident2 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=branch2)
        await incident2.delete(db=db)

        # Query on branch2 — the allocation is still active on main, so it should appear
        query = await NumberPoolGetAllocated.init(db=db, pool=incident_pool, branch=branch2, branch_agnostic=True)
        await query.execute(db=db)
        results = query.get_data()

        allocated_values = sorted([r.value for r in results])
        assert allocated_values == [1, 2, 3], (
            f"Expected allocation (value=2) to remain visible (active on main), got {allocated_values}"
        )

    async def test_source_cleared_on_a_branch_leaves_the_allocation_reported(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """What a pool accounts for is its own record, not the source stored on the attribute."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPoolProtocol] = await NodeManager.query(
            db=db, schema=CoreNumberPoolProtocol, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        br1 = await create_branch(db=db, branch_name="br1")
        incident2 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=br1)
        incident2.get_attribute("number").clear_source()
        await incident2.save(db=db)

        for branch in (br1, default_branch):
            query = await NumberPoolGetAllocated.init(db=db, pool=incident_pool, branch=branch, branch_agnostic=True)
            await query.execute(db=db)
            allocated_values = sorted([r.value for r in query.get_data()])
            assert allocated_values == [1, 2, 3], f"Expected every allocation on {branch.name}, got {allocated_values}"

    async def test_source_cleared_on_the_allocating_branch_leaves_the_allocation_reported(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """Clearing the source where the number was allocated does not release it."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPoolProtocol] = await NodeManager.query(
            db=db, schema=CoreNumberPoolProtocol, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        incident2 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=default_branch)
        incident2.get_attribute("number").clear_source()
        await incident2.save(db=db)

        query = await NumberPoolGetAllocated.init(
            db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True
        )
        await query.execute(db=db)

        allocated_values = sorted([r.value for r in query.get_data()])
        assert allocated_values == [1, 2, 3], f"Expected value=2 to stay allocated, got {allocated_values}"

    async def test_source_cleared_on_two_branches_leaves_the_allocation_reported(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """A source cleared on a branch and then on main still leaves the number accounted for."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        br1 = await create_branch(db=db, branch_name="br1")

        incident2_on_br1 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=br1)
        incident2_on_br1.get_attribute("number").clear_source()
        await incident2_on_br1.save(db=db)

        incident2_on_main = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=default_branch)
        incident2_on_main.get_attribute("number").clear_source()
        await incident2_on_main.save(db=db)

        query = await NumberPoolGetAllocated.init(
            db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True
        )
        await query.execute(db=db)

        allocated_values = sorted([r.value for r in query.get_data()])
        assert allocated_values == [1, 2, 3], f"Expected value=2 to stay allocated, got {allocated_values}"

    async def test_source_reassigned_to_the_pool_on_a_branch_leaves_the_allocation_reported(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """Clearing and restoring the source leaves one record and one reported allocation."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        br1 = await create_branch(db=db, branch_name="br1")
        incident2_on_br1 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=br1)
        incident2_on_br1.get_attribute("number").clear_source()
        await incident2_on_br1.save(db=db)

        incident2_on_br1 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=br1)
        incident2_on_br1.get_attribute("number").set_source(incident_pool.get_id())
        await incident2_on_br1.save(db=db)

        incident2_on_main = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=default_branch)
        incident2_on_main.get_attribute("number").clear_source()
        await incident2_on_main.save(db=db)

        query = await NumberPoolGetAllocated.init(db=db, pool=incident_pool, branch=br1, branch_agnostic=True)
        await query.execute(db=db)

        results = query.get_data()
        allocated_values = sorted([r.value for r in results])
        assert allocated_values == [1, 2, 3], f"Expected value=2 to stay allocated, got {allocated_values}"
        assert len([r for r in results if r.value == 2]) == 1, "an allocation is reported once, whatever the source"

    async def test_merging_a_cleared_source_leaves_the_allocation_reported(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """Merging a branch that cleared the source does not release the number."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        pools: list[CoreNumberPool] = await NodeManager.query(
            db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        br1 = await create_branch(db=db, branch_name="br1-clear-then-merge")
        incident2_on_br1 = await NodeManager.get_one(db=db, id=incidents[1].get_id(), branch=br1)
        incident2_on_br1.get_attribute("number").clear_source()
        await incident2_on_br1.save(db=db)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=br1)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=br1)
        diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=br1)
        await diff_merger.merge_graph(at=Timestamp())

        query = await NumberPoolGetAllocated.init(
            db=db, pool=incident_pool, branch=default_branch, branch_agnostic=True
        )
        await query.execute(db=db)

        allocated_values = sorted([r.value for r in query.get_data()])
        assert allocated_values == [1, 2, 3], f"Expected value=2 to stay allocated, got {allocated_values}"


async def live_record_count(db: InfrahubDatabase, node_id: str, attribute_name: str) -> int:
    """How many reservation records the object's attribute carries right now."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        WITH DISTINCT a
        MATCH ()-[e:IS_RESERVED]->(a)
        WHERE e.status = "active" AND e.to IS NULL
        RETURN count(e) AS live
        """,
        params={"node_id": node_id, "attribute_name": attribute_name},
    )
    return int(results[0]["live"])


class TestNumberPoolChangeReserved:
    async def test_the_record_names_the_replacement_object_and_is_not_duplicated(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """Replacing an object moves the ledger onto the replacement without counting the number twice."""
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        request_schema = registry.schema.get_node_schema(name=REQUEST.kind, branch=default_branch)

        incidents = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=3)
        await create_objects(db=db, schema=request_schema, branch=default_branch.name, start=1, end=6)
        replaced = incidents[1]

        pools: list[CoreNumberPoolProtocol] = await NodeManager.query(
            db=db, schema=CoreNumberPoolProtocol, branch=default_branch
        )
        assert len(pools) == 2
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        reservations_before = await get_reservations(db=db, pool=incident_pool, branch=default_branch)
        assert len(reservations_before) == 3
        assert reservations_before[replaced.get_id()] == 2

        replacement_started_at = Timestamp()
        await replaced.delete(db=db)
        replacement = (await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=4, end=4))[
            0
        ]
        assert replacement.get_attribute("number").value == 2, (
            "the replacement takes the number the replaced object released"
        )

        query = await NumberPoolChangeReserved.init(
            db=db,
            existing_node_id=replaced.get_id(),
            new_node_id=replacement.get_id(),
            existing_identifier=replaced.get_id(),
            new_identifier=replacement.get_id(),
            not_closed_before=replacement_started_at,
            branch=default_branch,
        )
        await query.execute(db=db)

        reservations_after = await get_reservations(db=db, pool=incident_pool, branch=default_branch)
        assert replaced.get_id() not in reservations_after, "the replaced object no longer holds the number"
        assert reservations_after[replacement.get_id()] == 2
        assert len(reservations_after) == 3
        assert await live_record_count(db=db, node_id=replacement.get_id(), attribute_name="number") == 1, (
            "a replacement that already holds a record from the pool must not acquire a second one"
        )

    async def test_the_anchors_and_the_identifiers_are_read_independently(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """Which attributes are touched comes from the anchors; what the record says comes from the identifiers.

        Driven with identifiers that are not the anchors' uuids, which is the only way to tell the
        two apart. Nothing arranges them that way in production, and nothing should have to.
        """
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)
        source, target = await create_objects(db=db, schema=incident_schema, branch=default_branch.name, start=1, end=2)

        await db.execute_query(
            query="""
            MATCH (:Node {uuid: $source_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "number"})
            WITH DISTINCT a
            MATCH ()-[record:IS_RESERVED]->(a)
            WHERE record.to IS NULL
            SET record.identifier = $borrowed
            """,
            params={"source_id": source.get_id(), "borrowed": "borrowed-label"},
        )
        await db.execute_query(
            query="""
            MATCH (:Node {uuid: $target_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "number"})
            WITH DISTINCT a
            MATCH ()-[record:IS_RESERVED]->(a)
            WHERE record.to IS NULL
            SET record.to = $at
            """,
            params={"target_id": target.get_id(), "at": Timestamp().to_string()},
        )

        query = await NumberPoolChangeReserved.init(
            db=db,
            existing_node_id=source.get_id(),
            new_node_id=target.get_id(),
            existing_identifier="borrowed-label",
            new_identifier="relabelled",
            not_closed_before=Timestamp("2000-01-01"),
            branch=default_branch,
        )
        await query.execute(db=db)

        assert await live_record_count(db=db, node_id=target.get_id(), attribute_name="number") == 1, (
            "the move must write a record on the vertex the new anchor names"
        )
        moved = await reservation_and_value_edges(db=db, node_id=target.get_id(), attribute_name="number")
        assert moved["record"]["identifier"] == "relabelled", (
            "the moved record carries the identifier it was given, not the uuid of the vertex it landed on"
        )
        assert await live_record_count(db=db, node_id=source.get_id(), attribute_name="number") == 1, (
            "the record found through the source anchor stays open for branches that predate the move"
        )
        kept = await reservation_and_value_edges(db=db, node_id=source.get_id(), attribute_name="number")
        assert kept["record"]["identifier"] == "borrowed-label", (
            "the record left behind keeps its own identifier rather than the one the move was given"
        )


async def reservation_and_value_edges(db: InfrahubDatabase, node_id: str, attribute_name: str) -> dict[str, Any]:
    """The live reservation record on the object's attribute, beside the edge carrying its value."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        WITH DISTINCT a
        MATCH (pool)-[record:IS_RESERVED]->(a)-[value:HAS_VALUE]->()
        WHERE record.status = "active" AND record.to IS NULL
        RETURN properties(record) AS record, value.from AS value_from, pool.uuid AS pool_id
        """,
        params={"node_id": node_id, "attribute_name": attribute_name},
    )
    return dict(results[0])


class TestCreateRecordsItsReservation:
    async def test_a_create_writes_the_value_and_its_record_in_one_step(
        self,
        db: InfrahubDatabase,
        register_test_schema: SchemaBranch,
        default_branch: Branch,
        run_number_pool_validation: None,
    ) -> None:
        """A created object reaches the graph with its number and the record accounting for it at once.

        The record is written by the query that writes the value, so no separate ledger write is
        issued. Were the value to land on its own, the number would read as free and the next object
        would be handed the same one.
        """
        incident_schema = registry.schema.get_node_schema(name=INCIDENT.kind, branch=default_branch)

        counting_db = CountingInfrahubDatabase.from_db(db=db)
        first = await Node.init(db=counting_db, schema=incident_schema, branch=default_branch.name)
        await first.new(db=counting_db, title="Incident #1")
        await first.save(db=counting_db)

        assert counting_db.count_for(NodeCreateAllQuery.name) == 1
        assert counting_db.count_for(NumberPoolSetReserved.name) == 0, (
            "separate reservation query should not be executed"
        )

        first_number = first.get_attribute(name="number").value
        assert first_number is not None

        pools: list[CoreNumberPoolProtocol] = await NodeManager.query(
            db=db, schema=CoreNumberPoolProtocol, branch=default_branch
        )
        incident_pool = next(pool for pool in pools if pool.get_attribute("node").value == INCIDENT.kind)

        assert await live_record_count(db=db, node_id=first.get_id(), attribute_name="number") == 1
        reservations = await get_reservations(db=db, pool=incident_pool, branch=default_branch)
        assert reservations == {first.get_id(): first_number}
        assert await get_used_numbers_in_pool(db=db, pool=incident_pool, branch=default_branch) == [first_number]

        edges = await reservation_and_value_edges(db=db, node_id=first.get_id(), attribute_name="number")
        assert edges["pool_id"] == incident_pool.get_id()
        assert edges["record"]["from"] == edges["value_from"], (
            "the record and the value must begin at the same instant, leaving no window between them"
        )
        assert edges["record"] == {
            "branch": GLOBAL_BRANCH_NAME,
            "branch_level": 1,
            "status": "active",
            "from": edges["value_from"],
            "identifier": first.get_id(),
            "provenance": PoolRecordProvenance.ALLOCATED.value,
        }

        second = await Node.init(db=db, schema=incident_schema, branch=default_branch.name)
        await second.new(db=db, title="Incident #2")
        await second.save(db=db)
        assert second.get_attribute(name="number").value != first_number, (
            "the number the first object holds must not be handed out again"
        )
