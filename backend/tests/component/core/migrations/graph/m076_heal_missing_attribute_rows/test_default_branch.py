import re
from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m076_heal_missing_attribute_rows import Migration076
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import verify_graph

from .conftest import (
    CAR_ATTRIBUTE_NAMES,
    INHERITED_CAR_ATTRIBUTE_NAMES,
    build_generic,
    build_inheriting_kind,
    count_branch_level_attribute_edges,
    create_damaged_car,
    create_damaged_node,
    create_healthy_car,
    delete_attribute_rows,
    drop_registry_schema,
    get_active_attribute_edge_details,
    get_attribute_row_edge_placements,
    recording_console,
    simulate_rebase,
    tombstone_attribute,
)


@dataclass(frozen=True)
class SeededDamage:
    healthy_uuid: str
    damaged_uuids: tuple[str, str]
    tombstoned_uuid: str
    tombstoned_attribute_uuid: str
    deleted_at: Timestamp
    branch: Branch


@dataclass(frozen=True)
class HealRun:
    errors: list[str]
    nbr_migrations_executed: int
    heal_at: Timestamp
    console_output: str


class TestDefaultBranchHeal:
    """One damaged default branch plus a pre-heal fork, healed once with two-row chunks.

    The class runs the migration twice: the default-branch pass in the ``healed``
    fixture and the rebased branch's pass in its own test. Methods relying on the
    un-healed state run first — they must not request ``healed``, which triggers
    the repair on first use. The schema-mutating test runs last.
    """

    @pytest.fixture(scope="class")
    async def seeded(self, db: InfrahubDatabase, asset_schema_class: Branch) -> SeededDamage:
        branch = asset_schema_class
        healthy = await create_healthy_car(
            db=db, branch=branch, name="healthy", created_at=Timestamp().subtract(seconds=30)
        )
        damaged_1 = await create_damaged_car(db=db, branch=branch, created_at=Timestamp().subtract(seconds=240))
        damaged_2 = await create_damaged_car(db=db, branch=branch, created_at=Timestamp().subtract(seconds=240))

        tombstoned = await create_healthy_car(
            db=db, branch=branch, name="tombstoned", created_at=Timestamp().subtract(seconds=30)
        )
        deleted_at = Timestamp().subtract(seconds=10)
        tombstoned_attribute_uuid = await tombstone_attribute(
            db=db, branch=branch, node_uuid=tombstoned.get_id(), attribute_name="status", deleted_at=deleted_at
        )

        user_branch = await create_branch(db=db, branch_name="branched-before-heal")

        return SeededDamage(
            healthy_uuid=healthy.get_id(),
            damaged_uuids=(damaged_1, damaged_2),
            tombstoned_uuid=tombstoned.get_id(),
            tombstoned_attribute_uuid=tombstoned_attribute_uuid,
            deleted_at=deleted_at,
            branch=user_branch,
        )

    @pytest.fixture(scope="class")
    async def healed(self, db: InfrahubDatabase, seeded: SeededDamage) -> HealRun:
        heal_at = Timestamp()
        console = recording_console()
        # To simulate the cold start for running a migration via the CLI
        drop_registry_schema()
        migration = Migration076(repair_batch_size=2)
        result = await migration.execute(migration_input=MigrationInput(db=db, at=heal_at, console=console))
        return HealRun(
            errors=result.errors,
            nbr_migrations_executed=result.nbr_migrations_executed,
            heal_at=heal_at,
            console_output=console.export_text(),
        )

    async def test_validation_reports_damage_before_heal(
        self, db: InfrahubDatabase, asset_schema_class: Branch, seeded: SeededDamage
    ) -> None:
        # Without the repair pass the invariant is violated: validation must fail
        # with actionable per-kind detail, which is what fails the upgrade.
        validation_result = await Migration076.init().validate_migration(db=db)
        assert validation_result.errors == [
            "TestCar: 5 missing attribute row(s) across 3 node(s) on branch "
            f"{asset_schema_class.name} (attributes: asset_tag, status)"
        ]

    def test_result_counts(self, healed: HealRun) -> None:
        assert healed.errors == []
        # 2 damaged nodes x 2 inherited attributes + 1 tombstoned status
        assert healed.nbr_migrations_executed == 5

    def test_console_narrates_exact_counts(self, healed: HealRun, asset_schema_class: Branch) -> None:
        branch_name = asset_schema_class.name
        # The audited total and the position within it depend on how many kinds the branch
        # carries, which for a migration run from the command line includes the core models.
        # The repair counts below are the part that has to be exact.
        assert re.search(
            rf"Branch {branch_name}: auditing \d+ kind\(s\) with inherited attributes", healed.console_output
        )
        assert re.search(
            r"\(\d+/\d+\) TestCar: 5 missing attribute row\(s\) across 3 node\(s\); repairing", healed.console_output
        )
        assert "TestCar.asset_tag: created 2 row(s)" in healed.console_output
        # 3 damaged status rows over two-row chunks: cumulative progress, then the total
        assert "TestCar.status: created 2/3 row(s)" in healed.console_output
        assert "TestCar.status: created 3/3 row(s)" in healed.console_output
        assert "TestCar.status: created 3 row(s)" in healed.console_output
        assert f"Branch {branch_name}: repaired 5 attribute row(s) across 1 kind(s)" in healed.console_output

    async def test_validation_clean_after_heal(self, db: InfrahubDatabase, healed: HealRun) -> None:
        validation_result = await Migration076.init().validate_migration(db=db)
        assert validation_result.errors == []

    async def test_damaged_nodes_fully_healed(
        self, db: InfrahubDatabase, asset_schema_class: Branch, seeded: SeededDamage, healed: HealRun
    ) -> None:
        heal_row = (asset_schema_class.name, healed.heal_at.to_string())
        for node_uuid in seeded.damaged_uuids:
            node = await NodeManager.get_one(db=db, branch=asset_schema_class, id=node_uuid)
            assert node is not None

            status_attr = node.get_attribute(name="status")
            assert status_attr.id is not None
            assert status_attr.value == "active"
            assert status_attr.is_default is True

            # Mandatory inherited attributes without a default are healed as null-valued rows
            asset_tag_attr = node.get_attribute(name="asset_tag")
            assert asset_tag_attr.id is not None
            assert asset_tag_attr.value is None

            # The kind's own local attribute is out of the audit: missing rows can only
            # stem from inheritance changes, so only generic-inherited attributes heal
            assert node.get_attribute(name="name").id is None

            edge_details = await get_active_attribute_edge_details(
                db=db, node_uuid=node_uuid, attribute_names=CAR_ATTRIBUTE_NAMES
            )
            assert edge_details == dict.fromkeys(INHERITED_CAR_ATTRIBUTE_NAMES, heal_row)

    async def test_tombstoned_attribute_healed_as_new_row(
        self, db: InfrahubDatabase, asset_schema_class: Branch, seeded: SeededDamage, healed: HealRun
    ) -> None:
        # The tombstone edge stays open — deleted edges never carry a `to` time — and
        # the re-created attribute is a brand-new vertex whose newer active edge wins
        # the latest-edge resolution.
        tombstone_query = """
        MATCH (n:Node { uuid: $uuid })-[r:HAS_ATTRIBUTE { status: "deleted" }]->(:Attribute { name: "status" })
        RETURN r.from AS from_time, r.to AS to_time
        """
        tombstone_results = await db.execute_query(query=tombstone_query, params={"uuid": seeded.tombstoned_uuid})
        assert len(tombstone_results) == 1
        assert tombstone_results[0]["from_time"] == seeded.deleted_at.to_string()
        assert tombstone_results[0]["to_time"] is None

        node = await NodeManager.get_one(db=db, branch=asset_schema_class, id=seeded.tombstoned_uuid)
        assert node is not None
        status_attr = node.get_attribute(name="status")
        assert status_attr.id is not None
        assert status_attr.id != seeded.tombstoned_attribute_uuid
        assert status_attr.value == "active"
        assert status_attr.is_default is True

    async def test_healthy_node_untouched(
        self, db: InfrahubDatabase, asset_schema_class: Branch, seeded: SeededDamage, healed: HealRun
    ) -> None:
        node = await NodeManager.get_one(db=db, branch=asset_schema_class, id=seeded.healthy_uuid)
        assert node is not None
        assert node.get_attribute(name="name").value == "healthy"
        assert node.get_attribute(name="asset_tag").value == "tag-healthy"
        for edge_branch, from_time in (
            await get_active_attribute_edge_details(
                db=db, node_uuid=seeded.healthy_uuid, attribute_names=CAR_ATTRIBUTE_NAMES
            )
        ).values():
            assert edge_branch == asset_schema_class.name
            assert Timestamp(from_time) < healed.heal_at

    async def test_branch_forked_before_heal_cannot_see_healed_rows(
        self, db: InfrahubDatabase, seeded: SeededDamage, healed: HealRun
    ) -> None:
        # The healed rows postdate the branch point. This is the accepted trade-off
        # of healing at run time; the branch reads them after its rebase.
        node = await NodeManager.get_one(db=db, branch=seeded.branch, id=seeded.damaged_uuids[0])
        assert node is not None
        assert node.get_attribute(name="status").id is None

    async def test_updates_to_healed_attributes_persist(
        self, db: InfrahubDatabase, asset_schema_class: Branch, seeded: SeededDamage, healed: HealRun
    ) -> None:
        repaired = await NodeManager.get_one(db=db, branch=asset_schema_class, id=seeded.damaged_uuids[0])
        repaired.get_attribute(name="status").value = "maintenance"
        repaired.get_attribute(name="asset_tag").value = "tag-repaired"
        await repaired.save(db=db)

        refreshed = await NodeManager.get_one(db=db, branch=asset_schema_class, id=seeded.damaged_uuids[0])
        assert refreshed.get_attribute(name="status").value == "maintenance"
        assert refreshed.get_attribute(name="status").is_default is False
        assert refreshed.get_attribute(name="asset_tag").value == "tag-repaired"

    async def test_rebased_branch_pass_writes_nothing(
        self, db: InfrahubDatabase, seeded: SeededDamage, healed: HealRun
    ) -> None:
        await simulate_rebase(db=db, branch=seeded.branch)

        # The branch carries no inheritance of its own beyond the default branch's
        # schema, so its pass audits no kinds at all and writes nothing
        branch_console = recording_console()
        branch_result = await Migration076.init().execute_against_branch(
            migration_input=MigrationInput(db=db, console=branch_console), branch=seeded.branch
        )
        assert branch_result.errors == []
        assert branch_result.nbr_migrations_executed == 0
        assert (
            f"Branch {seeded.branch.name}: auditing 0 kind(s) with inherited attributes" in branch_console.export_text()
        )
        assert await count_branch_level_attribute_edges(db=db, branch_name=seeded.branch.name) == 0

        node = await NodeManager.get_one(db=db, branch=seeded.branch, id=seeded.damaged_uuids[1])
        assert node is not None
        status_attr = node.get_attribute(name="status")
        assert status_attr.id is not None
        assert status_attr.value == "active"

    async def test_second_run_performs_zero_writes(self, db: InfrahubDatabase, healed: HealRun) -> None:
        # Everything is healthy now: the rerun is the healthy-install case too
        snapshotter = DbSnapshotter(db)
        before = await snapshotter.snapshot()

        console = recording_console()
        second_result = await Migration076.init().execute(migration_input=MigrationInput(db=db, console=console))
        assert second_result.errors == []
        assert second_result.nbr_migrations_executed == 0

        console_output = console.export_text()
        assert "nothing to repair." in console_output
        assert "repairing" not in console_output

        assert await snapshotter.snapshot() == before

    async def test_graph_left_valid(self, db: InfrahubDatabase, healed: HealRun) -> None:
        await verify_graph(db=db)

    async def test_removed_schema_attribute_neither_re_added_nor_reported(
        self, db: InfrahubDatabase, asset_schema_class: Branch, seeded: SeededDamage, healed: HealRun
    ) -> None:
        # Destructive final test: removes an attribute from the persisted schema
        await tombstone_attribute(
            db=db,
            branch=asset_schema_class,
            node_uuid=seeded.healthy_uuid,
            attribute_name="status",
            deleted_at=Timestamp(),
        )
        generic_db = registry.schema.get(name="TestAsset", branch=asset_schema_class.name, duplicate=False)
        status_attribute = generic_db.get_attribute(name="status")
        assert status_attribute.id is not None
        attribute_node = await NodeManager.get_one(db=db, branch=asset_schema_class, id=status_attribute.id)
        assert attribute_node is not None
        await attribute_node.delete(db=db, at=Timestamp())

        # The audit follows the persisted schema: reload it so the removal is visible
        reloaded_schema = await registry.schema.load_schema_from_db(db=db, branch=asset_schema_class)
        registry.schema.set_schema_branch(name=asset_schema_class.name, schema=reloaded_schema)
        assert "status" not in reloaded_schema.get(name="TestCar", duplicate=False).attribute_names

        snapshotter = DbSnapshotter(db)
        before = await snapshotter.snapshot()

        migration = Migration076.init()
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert execution_result.errors == []
        assert execution_result.nbr_migrations_executed == 0

        validation_result = await migration.validate_migration(db=db)
        assert validation_result.errors == []

        assert await snapshotter.snapshot() == before

        # The tombstone stays the final word on the removed attribute
        edge_details = await get_active_attribute_edge_details(
            db=db, node_uuid=seeded.healthy_uuid, attribute_names=CAR_ATTRIBUTE_NAMES
        )
        assert set(edge_details) == {"name", "asset_tag"}


async def test_multiple_generics_defining_same_attribute_use_effective_schema(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    generic_a = build_generic(
        name="Asset",
        attributes=[AttributeSchema(name="status", kind="Text", default_value="from-asset", optional=True)],
    )
    generic_b = build_generic(
        name="Device",
        attributes=[AttributeSchema(name="status", kind="Text", default_value="from-device", optional=True)],
    )
    car = build_inheriting_kind(name="Car", inherit_from=["TestAsset", "TestDevice"])
    schema_branch = registry.schema.register_schema(
        schema=SchemaRoot(generics=[generic_a, generic_b], nodes=[car]), branch=default_branch.name
    )
    await registry.schema.load_schema_to_db(
        schema=schema_branch,
        branch=default_branch,
        db=db,
        at=Timestamp().subtract(seconds=120),
        limit=["TestAsset", "TestDevice", "TestCar"],
    )
    default_branch.update_schema_hash()

    # Inheritance processing applies the generics in inherit_from order, each later
    # one updating the inherited attribute: the last listed generic's definition wins
    effective_default = schema_branch.get(name="TestCar", duplicate=False).get_attribute(name="status").default_value
    assert effective_default == "from-device"

    node = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await node.new(db=db, name="multi-generic")
    await node.save(db=db, at=Timestamp().subtract(seconds=240))
    await delete_attribute_rows(db=db, node_uuid=node.get_id(), attribute_names=["name", "status"])

    migration = Migration076.init()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert execution_result.errors == []
    assert execution_result.nbr_migrations_executed == 1

    validation_result = await migration.validate_migration(db=db)
    assert validation_result.errors == []

    # Exactly one row exists (the edge-details helper rejects duplicates) and it
    # carries the processed schema's effective definition
    edge_details = await get_active_attribute_edge_details(
        db=db, node_uuid=node.get_id(), attribute_names=("name", "status")
    )
    assert set(edge_details) == {"status"}

    healed = await NodeManager.get_one(db=db, branch=default_branch, id=node.get_id())
    assert healed is not None
    status_attr = healed.get_attribute(name="status")
    assert status_attr.id is not None
    assert status_attr.value == effective_default
    assert status_attr.is_default is True

    await verify_graph(db=db)


async def test_damaged_profile_and_template_instances_healed(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    generic = build_generic(
        name="Asset",
        attributes=[
            AttributeSchema(name="status", kind="Text", default_value="active", optional=True),
            AttributeSchema(name="serial", kind="Text", optional=False, unique=True),
        ],
    )
    car = build_inheriting_kind(name="Car", inherit_from=["TestAsset"])
    schema_branch = registry.schema.register_schema(
        schema=SchemaRoot(generics=[generic], nodes=[car]), branch=default_branch.name
    )
    await registry.schema.load_schema_to_db(
        schema=schema_branch,
        branch=default_branch,
        db=db,
        at=Timestamp().subtract(seconds=120),
        limit=["TestAsset", "TestCar"],
    )
    default_branch.update_schema_hash()

    created_at = Timestamp().subtract(seconds=240)
    damaged_node = await create_damaged_node(
        db=db, branch=default_branch, labels="TestCar:TestAsset", kind="TestCar", created_at=created_at
    )
    damaged_profile = await create_damaged_node(
        db=db, branch=default_branch, labels="ProfileTestCar", kind="ProfileTestCar", created_at=created_at
    )
    damaged_template = await create_damaged_node(
        db=db, branch=default_branch, labels="TemplateTestCar", kind="TemplateTestCar", created_at=created_at
    )

    migration = Migration076.init()

    # Detection covers profile and template instances too
    validation_before = await migration.validate_migration(db=db)
    assert validation_before.errors == [
        f"TestCar: 4 missing attribute row(s) across 3 node(s) on branch {default_branch.name} "
        "(attributes: serial, status)"
    ]

    heal_at = Timestamp()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=heal_at))
    assert execution_result.errors == []
    # concrete instance: serial + status; profile and template instances: status only
    assert execution_result.nbr_migrations_executed == 4

    validation_result = await migration.validate_migration(db=db)
    assert validation_result.errors == []

    # The unique attribute is healed on the concrete instance only: profiles and
    # templates never carry unique attributes, so no row may be created there.
    heal_row = (default_branch.name, heal_at.to_string())
    assert await get_active_attribute_edge_details(db=db, node_uuid=damaged_node) == {
        "serial": heal_row,
        "status": heal_row,
    }
    assert await get_active_attribute_edge_details(db=db, node_uuid=damaged_profile) == {
        "status": heal_row,
    }
    assert await get_active_attribute_edge_details(db=db, node_uuid=damaged_template) == {
        "status": heal_row,
    }

    second_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert second_result.errors == []
    assert second_result.nbr_migrations_executed == 0


async def test_agnostic_attribute_healed_on_global_branch(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    generic = build_generic(
        name="Asset",
        attributes=[
            AttributeSchema(name="status", kind="Text", default_value="active", optional=True),
            AttributeSchema(name="serial", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC),
        ],
    )
    car = build_inheriting_kind(name="Car", inherit_from=["TestAsset"])
    schema_branch = registry.schema.register_schema(
        schema=SchemaRoot(generics=[generic], nodes=[car]), branch=default_branch.name
    )
    await registry.schema.load_schema_to_db(
        schema=schema_branch,
        branch=default_branch,
        db=db,
        at=Timestamp().subtract(seconds=120),
        limit=["TestAsset", "TestCar"],
    )
    default_branch.update_schema_hash()

    node = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await node.new(db=db, name="agnostic-car")
    await node.save(db=db, at=Timestamp().subtract(seconds=240))
    await delete_attribute_rows(db=db, node_uuid=node.get_id(), attribute_names=["name", "serial", "status"])
    damaged = node.get_id()

    global_edges_before = await count_branch_level_attribute_edges(db=db, branch_name=GLOBAL_BRANCH_NAME)

    heal_at = Timestamp()
    migration = Migration076.init()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=heal_at))
    assert execution_result.errors == []
    assert execution_result.nbr_migrations_executed == 2

    validation_result = await migration.validate_migration(db=db)
    assert validation_result.errors == []

    # The agnostic attribute's whole row lives on the global branch; aware rows
    # stay on the default branch
    heal_at_str = heal_at.to_string()
    assert await get_active_attribute_edge_details(
        db=db, node_uuid=damaged, attribute_names=CAR_ATTRIBUTE_NAMES + ("serial",)
    ) == {
        "status": (default_branch.name, heal_at_str),
        "serial": (GLOBAL_BRANCH_NAME, heal_at_str),
    }
    assert await get_attribute_row_edge_placements(db=db, node_uuid=damaged, attribute_name="serial") == {
        ("HAS_ATTRIBUTE", GLOBAL_BRANCH_NAME, 1),
        ("HAS_VALUE", GLOBAL_BRANCH_NAME, 1),
        ("IS_PROTECTED", GLOBAL_BRANCH_NAME, 1),
    }
    assert await count_branch_level_attribute_edges(db=db, branch_name=GLOBAL_BRANCH_NAME) == global_edges_before + 3

    # The healed rows are readable from the default branch and from a branch
    # created after the heal
    branch = await create_branch(db=db, branch_name="forked-after-heal")
    assert await count_branch_level_attribute_edges(db=db, branch_name=branch.name) == 0
    for read_branch in (default_branch, branch):
        read_node = await NodeManager.get_one(db=db, branch=read_branch, id=damaged)
        assert read_node is not None
        serial_attr = read_node.get_attribute(name="serial")
        assert serial_attr.id is not None
        assert serial_attr.value is None
        status_attr = read_node.get_attribute(name="status")
        assert status_attr.id is not None
        assert status_attr.value == "active"

    second_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert second_result.errors == []
    assert second_result.nbr_migrations_executed == 0

    await verify_graph(db=db)
