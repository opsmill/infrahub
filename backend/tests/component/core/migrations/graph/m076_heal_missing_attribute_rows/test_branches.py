from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m076_heal_missing_attribute_rows import Migration076
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import verify_graph

from .conftest import (
    CAR_ATTRIBUTE_NAMES,
    build_asset_schema,
    build_inheriting_kind,
    get_active_attribute_edge_details,
    recording_console,
)


async def count_active_branch_attribute_edges(
    db: InfrahubDatabase, node_uuid: str, branch_name: str, attribute_names: list[str]
) -> int:
    query = """
    MATCH (n:Node { uuid: $uuid })-[r:HAS_ATTRIBUTE { status: "active", branch: $branch_name }]->(a:Attribute)
    WHERE r.to IS NULL AND a.name IN $names
    RETURN count(r) AS edge_count
    """
    results = await db.execute_query(
        query=query, params={"uuid": node_uuid, "branch_name": branch_name, "names": attribute_names}
    )
    return results[0]["edge_count"]


@dataclass(frozen=True)
class BranchOriginSeed:
    branch: Branch
    car_uuid: str
    car_created_at: Timestamp


@dataclass(frozen=True)
class BranchHealRun:
    default_errors: list[str]
    default_nbr: int
    branch_errors: list[str]
    branch_nbr: int
    heal_at: Timestamp
    branch_console_output: str


class TestBranchOriginHeal:
    """A kind gains its generic on a branch only; the branch pass repairs it there.

    The class runs the migration twice in one fixture: the default-branch pass
    (which must audit nothing — the default schema never defined the attributes)
    and the branch's own pass.
    """

    @pytest.fixture(scope="class")
    async def seeded(self, db: InfrahubDatabase, default_branch_scope_class: Branch) -> BranchOriginSeed:
        default = default_branch_scope_class
        registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default.name)
        base_schema = SchemaRoot(nodes=[build_inheriting_kind(name="Car", inherit_from=[])])
        base_schema_branch = registry.schema.register_schema(schema=base_schema, branch=default.name)
        await registry.schema.load_schema_to_db(
            schema=base_schema_branch, branch=default, db=db, at=Timestamp().subtract(seconds=300), limit=["TestCar"]
        )
        default.update_schema_hash()

        car_created_at = Timestamp().subtract(seconds=240)
        car = await Node.init(db=db, schema="TestCar", branch=default)
        await car.new(db=db, name="main-car")
        await car.save(db=db, at=car_created_at)

        branch = await create_branch(db=db, branch_name="inherit-on-branch")

        # The kind gains the generic (and its attributes) on the branch only, without
        # attribute rows ever being created — the damage shape this migration repairs.
        branch_schema = registry.schema.register_schema(schema=build_asset_schema(), branch=branch.name)
        await registry.schema.load_schema_to_db(
            schema=branch_schema,
            branch=branch,
            db=db,
            at=Timestamp().subtract(seconds=60),
            limit=["TestAsset", "TestCar"],
        )
        branch.update_schema_hash()
        await branch.save(db=db)

        return BranchOriginSeed(branch=branch, car_uuid=car.get_id(), car_created_at=car_created_at)

    @pytest.fixture(scope="class")
    async def healed(self, db: InfrahubDatabase, seeded: BranchOriginSeed) -> BranchHealRun:
        migration = Migration076.init()
        default_result = await migration.execute(migration_input=MigrationInput(db=db))

        heal_at = Timestamp()
        branch_console = recording_console()
        branch_result = await migration.execute_against_branch(
            migration_input=MigrationInput(db=db, at=heal_at, console=branch_console), branch=seeded.branch
        )
        return BranchHealRun(
            default_errors=default_result.errors,
            default_nbr=default_result.nbr_migrations_executed,
            branch_errors=branch_result.errors,
            branch_nbr=branch_result.nbr_migrations_executed,
            heal_at=heal_at,
            branch_console_output=branch_console.export_text(),
        )

    async def test_default_pass_audits_nothing(self, db: InfrahubDatabase, healed: BranchHealRun) -> None:
        # The default branch's schema never defined the attributes
        assert healed.default_errors == []
        assert healed.default_nbr == 0

        validation_result = await Migration076.init().validate_migration(db=db)
        assert validation_result.errors == []

    def test_branch_pass_audits_only_the_changed_kind(self, seeded: BranchOriginSeed, healed: BranchHealRun) -> None:
        assert healed.branch_errors == []
        # 1 node x 2 inherited attributes, at branch level
        assert healed.branch_nbr == 2
        assert (
            f"Branch {seeded.branch.name}: auditing 1 kind(s) with inherited attributes" in healed.branch_console_output
        )

    async def test_branch_reads_healed_attributes(
        self, db: InfrahubDatabase, seeded: BranchOriginSeed, healed: BranchHealRun
    ) -> None:
        node = await NodeManager.get_one(db=db, branch=seeded.branch, id=seeded.car_uuid)
        assert node is not None
        status_attr = node.get_attribute(name="status")
        assert status_attr.id is not None
        assert status_attr.value == "active"
        assert status_attr.is_default is True
        asset_tag_attr = node.get_attribute(name="asset_tag")
        assert asset_tag_attr.id is not None
        assert asset_tag_attr.value is None

    async def test_healed_rows_are_branch_level_only(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        seeded: BranchOriginSeed,
        healed: BranchHealRun,
    ) -> None:
        edges = await get_active_attribute_edge_details(
            db=db, node_uuid=seeded.car_uuid, attribute_names=CAR_ATTRIBUTE_NAMES
        )
        heal_at_str = healed.heal_at.to_string()
        assert edges == {
            "status": (seeded.branch.name, heal_at_str),
            "asset_tag": (seeded.branch.name, heal_at_str),
            "name": (default_branch_scope_class.name, seeded.car_created_at.to_string()),
        }
        assert (
            await count_active_branch_attribute_edges(
                db=db,
                node_uuid=seeded.car_uuid,
                branch_name=default_branch_scope_class.name,
                attribute_names=["status", "asset_tag"],
            )
            == 0
        )
        default_node = await NodeManager.get_one(db=db, branch=default_branch_scope_class, id=seeded.car_uuid)
        assert default_node is not None
        assert default_node.get_attribute(name="name").value == "main-car"

    async def test_second_branch_pass_performs_zero_writes(
        self, db: InfrahubDatabase, seeded: BranchOriginSeed, healed: BranchHealRun
    ) -> None:
        snapshotter = DbSnapshotter(db)
        before = await snapshotter.snapshot()

        second_result = await Migration076.init().execute_against_branch(
            migration_input=MigrationInput(db=db), branch=seeded.branch
        )
        assert second_result.errors == []
        assert second_result.nbr_migrations_executed == 0
        assert await snapshotter.snapshot() == before

    async def test_graph_left_valid(self, db: InfrahubDatabase, healed: BranchHealRun) -> None:
        await verify_graph(db=db)
