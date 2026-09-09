from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.migrations.graph.m076_heal_missing_attribute_rows import Migration076
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from tests.db_snapshot import DbSnapshotter

from .conftest import (
    build_generic,
    build_inheriting_kind,
    build_rack_unit_attribute,
    create_damaged_node,
    create_schema_number_pool,
    get_active_attribute_edge_details,
    get_pool_attribute_row_shape,
    get_schema_pools,
    load_server_schema,
    recording_console,
    simulate_rebase,
)


@dataclass(frozen=True)
class PoolSeed:
    pool_uuid: str
    runtime_server_uuid: str
    damaged_uuids: tuple[str, str, str]


@dataclass(frozen=True)
class PoolHealRun:
    errors: list[str]
    nbr_migrations_executed: int
    console_output: str


class TestNumberPoolHeal:
    """One pre-provisioned pool, one runtime-written server, three damaged ones, healed once."""

    @pytest.fixture(scope="class")
    async def seeded(self, db: InfrahubDatabase, default_branch_scope_class: Branch) -> PoolSeed:
        default = default_branch_scope_class
        registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default.name)
        registry.schema.register_schema(schema=SchemaRoot(**core_models), branch=default.name)

        pool = await create_schema_number_pool(db=db, node="TestAsset", node_attribute="rack_unit")
        await load_server_schema(db=db, default_branch=default, number_pool_id=pool.get_id())

        # One node gets its pool row through the regular write path, the others through the heal
        runtime_server = await Node.init(db=db, schema="TestServer", branch=default)
        await runtime_server.new(db=db, name="runtime")
        await runtime_server.save(db=db)

        damaged: list[str] = []
        for _ in range(3):
            damaged.append(
                await create_damaged_node(
                    db=db,
                    branch=default,
                    labels="TestServer:TestAsset",
                    kind="TestServer",
                    created_at=Timestamp().subtract(seconds=240),
                )
            )
        return PoolSeed(
            pool_uuid=pool.get_id(),
            runtime_server_uuid=runtime_server.get_id(),
            damaged_uuids=(damaged[0], damaged[1], damaged[2]),
        )

    @pytest.fixture(scope="class")
    async def healed(self, db: InfrahubDatabase, seeded: PoolSeed) -> PoolHealRun:
        console = recording_console()
        result = await Migration076.init().execute(migration_input=MigrationInput(db=db, console=console))
        return PoolHealRun(
            errors=result.errors,
            nbr_migrations_executed=result.nbr_migrations_executed,
            console_output=console.export_text(),
        )

    async def test_result_counts_and_console(self, db: InfrahubDatabase, healed: PoolHealRun) -> None:
        assert healed.errors == []
        # 3 damaged nodes x 1 pool-backed inherited attribute
        assert healed.nbr_migrations_executed == 3
        assert "TestServer: 3 missing attribute row(s) across 3 node(s); repairing" in healed.console_output
        assert "TestServer.rack_unit: allocated 3 pool value(s)" in healed.console_output

        validation_result = await Migration076.init().validate_migration(db=db)
        assert validation_result.errors == []

    async def test_single_pool_served_all_allocations(
        self, db: InfrahubDatabase, seeded: PoolSeed, healed: PoolHealRun
    ) -> None:
        pools = await get_schema_pools(db=db)
        assert len(pools) == 1
        assert pools[0].get_id() == seeded.pool_uuid
        assert pools[0].get_attribute(name="node").value == "TestAsset"
        assert pools[0].get_attribute(name="node_attribute").value == "rack_unit"

    async def test_distinct_values_sourced_from_the_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, seeded: PoolSeed, healed: PoolHealRun
    ) -> None:
        nodes = await NodeManager.get_many(
            db=db,
            branch=default_branch_scope_class,
            ids=[*seeded.damaged_uuids, seeded.runtime_server_uuid],
            include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE),
        )
        rack_units = {node_id: node.get_attribute(name="rack_unit").value for node_id, node in nodes.items()}
        assert set(rack_units) == {*seeded.damaged_uuids, seeded.runtime_server_uuid}
        assert all(isinstance(value, int) and 1 <= value <= 100 for value in rack_units.values())
        assert len(set(rack_units.values())) == 4
        assert rack_units[seeded.runtime_server_uuid] == 1
        assert {rack_units[uuid] for uuid in seeded.damaged_uuids} == {2, 3, 4}
        for node in nodes.values():
            assert node.get_attribute(name="rack_unit").source_id == seeded.pool_uuid

    async def test_healed_row_matches_runtime_row_shape(
        self, db: InfrahubDatabase, seeded: PoolSeed, healed: PoolHealRun
    ) -> None:
        runtime_shape, runtime_value = await get_pool_attribute_row_shape(
            db=db, node_uuid=seeded.runtime_server_uuid, attribute_name="rack_unit"
        )
        healed_shape, healed_value = await get_pool_attribute_row_shape(
            db=db, node_uuid=seeded.damaged_uuids[0], attribute_name="rack_unit"
        )

        # The healed row is structurally identical to the runtime-written row,
        # differing only in its allocated number
        assert healed_shape == runtime_shape
        assert healed_shape.edge_types == {"HAS_VALUE", "IS_PROTECTED", "HAS_SOURCE"}
        assert healed_shape.edge("HAS_VALUE").peer[1] is False
        assert healed_shape.edge("HAS_SOURCE").peer[1] == seeded.pool_uuid
        assert healed_value != runtime_value

    async def test_second_run_allocates_nothing_new(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, seeded: PoolSeed, healed: PoolHealRun
    ) -> None:
        nodes_before = await NodeManager.get_many(
            db=db, branch=default_branch_scope_class, ids=list(seeded.damaged_uuids)
        )
        values_before = {node_id: node.get_attribute(name="rack_unit").value for node_id, node in nodes_before.items()}

        second_result = await Migration076.init().execute(migration_input=MigrationInput(db=db))
        assert second_result.errors == []
        assert second_result.nbr_migrations_executed == 0

        assert len(await get_schema_pools(db=db)) == 1
        nodes_after = await NodeManager.get_many(
            db=db, branch=default_branch_scope_class, ids=list(seeded.damaged_uuids)
        )
        values_after = {node_id: node.get_attribute(name="rack_unit").value for node_id, node in nodes_after.items()}
        assert values_after == values_before

    async def test_graph_left_valid(self, db: InfrahubDatabase, healed: PoolHealRun) -> None:
        await verify_graph(db=db)


async def test_numberpool_missing_pool_upserted_and_healed(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_server_schema(db=db, default_branch=default_branch)

    damaged = await create_damaged_node(
        db=db,
        branch=default_branch,
        labels="TestServer:TestAsset",
        kind="TestServer",
        created_at=Timestamp().subtract(seconds=240),
    )

    assert await get_schema_pools(db=db) == []

    migration = Migration076.init()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert execution_result.errors == []
    assert execution_result.nbr_migrations_executed == 1

    validation_result = await migration.validate_migration(db=db)
    assert validation_result.errors == []

    # The pool was upserted the same way the schema change provisions it:
    # once, registered against the generic's kind
    pools = await get_schema_pools(db=db)
    assert len(pools) == 1
    assert pools[0].get_attribute(name="node").value == "TestAsset"
    assert pools[0].get_attribute(name="node_attribute").value == "rack_unit"

    node = await NodeManager.get_one(db=db, branch=default_branch, id=damaged)
    assert node is not None
    rack_unit_attr = node.get_attribute(name="rack_unit")
    assert rack_unit_attr.id is not None
    assert isinstance(rack_unit_attr.value, int)
    assert 1 <= rack_unit_attr.value <= 100

    # A rerun reuses the upserted pool
    second_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert second_result.errors == []
    assert second_result.nbr_migrations_executed == 0
    assert len(await get_schema_pools(db=db)) == 1

    await verify_graph(db=db)


async def test_branch_pool_allocations_follow_default_branch_allocations(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    await create_schema_number_pool(db=db, node="TestAsset", node_attribute="rack_unit")

    default_schema = SchemaRoot(
        generics=[build_generic(name="Asset", attributes=[build_rack_unit_attribute()])],
        nodes=[
            build_inheriting_kind(name="Server", inherit_from=["TestAsset"]),
            build_inheriting_kind(name="Car", inherit_from=[]),
        ],
    )
    default_schema_branch = registry.schema.register_schema(schema=default_schema, branch=default_branch.name)
    await registry.schema.load_schema_to_db(
        schema=default_schema_branch,
        branch=default_branch,
        db=db,
        at=Timestamp().subtract(seconds=300),
        limit=["TestAsset", "TestServer", "TestCar"],
    )
    default_branch.update_schema_hash()

    damaged_servers = [
        await create_damaged_node(
            db=db,
            branch=default_branch,
            labels="TestServer:TestAsset",
            kind="TestServer",
            created_at=Timestamp().subtract(seconds=240),
        )
        for _ in range(2)
    ]

    branch = await create_branch(db=db, branch_name="pool-follows-default")

    # On the branch, the other kind starts inheriting the same generic, so its
    # damage draws from the same pool as the default-branch damage
    car_with_inheritance = SchemaRoot(nodes=[build_inheriting_kind(name="Car", inherit_from=["TestAsset"])])
    branch_schema = registry.schema.register_schema(schema=car_with_inheritance, branch=branch.name)
    await registry.schema.load_schema_to_db(
        schema=branch_schema, branch=branch, db=db, at=Timestamp().subtract(seconds=60), limit=["TestCar"]
    )
    branch.update_schema_hash()
    await branch.save(db=db)

    damaged_car = await create_damaged_node(
        db=db, branch=branch, labels="TestCar:TestAsset", kind="TestCar", created_at=Timestamp().subtract(seconds=30)
    )

    migration = Migration076.init()

    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert execution_result.errors == []
    assert execution_result.nbr_migrations_executed == 2
    assert await get_active_attribute_edge_details(db=db, node_uuid=damaged_car) == {}

    validation_result = await migration.validate_migration(db=db)
    assert validation_result.errors == []

    await simulate_rebase(db=db, branch=branch)

    branch_result = await migration.execute_against_branch(migration_input=MigrationInput(db=db), branch=branch)
    assert branch_result.errors == []
    assert branch_result.nbr_migrations_executed == 1

    servers = await NodeManager.get_many(db=db, branch=default_branch, ids=damaged_servers)
    allocated = {node_id: node.get_attribute(name="rack_unit").value for node_id, node in servers.items()}
    assert set(allocated) == set(damaged_servers)
    healed_car = await NodeManager.get_one(db=db, branch=branch, id=damaged_car)
    assert healed_car is not None
    allocated[damaged_car] = healed_car.get_attribute(name="rack_unit").value

    # The branch allocation follows the default-branch ones: three values from
    # one pool, no overlap
    assert all(isinstance(value, int) and 1 <= value <= 100 for value in allocated.values())
    assert len(set(allocated.values())) == 3

    snapshotter = DbSnapshotter(db)
    before_second_run = await snapshotter.snapshot()
    second_result = await migration.execute_against_branch(migration_input=MigrationInput(db=db), branch=branch)
    assert second_result.errors == []
    assert second_result.nbr_migrations_executed == 0
    assert await snapshotter.snapshot() == before_second_run

    await verify_graph(db=db)
