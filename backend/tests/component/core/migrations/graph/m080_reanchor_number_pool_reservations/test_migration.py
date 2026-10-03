"""The number pool re-anchoring migration, run twice over one database holding every legacy shape.

Each case gets its own objects, and where a case would move a pool's figures, its own pool, so the
cases cannot mask one another. The fixture loads the database, runs the migration and its
validation, then runs both again; every test reads the state that leaves behind.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import GraphCheck, collect_graph_violations
from infrahub.pools.number import NumberUtilizationGetter
from tests.component.core.migrations.graph.m080_reanchor_number_pool_reservations.conftest import (
    POOL_END,
    POOL_START,
    TRACKED_ATTRIBUTE_NAME,
    MigrationRun,
    ReservationRecord,
    allocate_from_pool,
    attribute_id_of,
    convert_legacy_records,
    create_legacy_record,
    create_legacy_source_edge,
    create_pool,
    create_ticket,
    create_ticket_allocated_on_update,
    create_ticket_with_value,
    live_records,
    migrate_ticket_inheritance,
    rename_tracked_attribute,
    reservation_records,
    reservation_records_on_attribute,
    rewrite_records_to_legacy_shape,
    run_migration,
    set_branch_status,
    stored_source_pool_ids,
    update_tracked_value,
)
from tests.helpers.schema import TICKET

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.database import InfrahubDatabase

CARRIED_PROPERTIES = ("branch", "branch_level", "from", "to", "status", "identifier")
ORPHAN_IDENTIFIER = str(uuid.uuid4())
RENAMED_ATTRIBUTE_NAME = "renamed_after_allocation"
UPDATED_VALUE = 90
UPDATED_AFTER_BRANCHING_VALUE = 91
BRANCH_VALUES = {"branch_updated_main_updated": 92, "branch_updated_main_deleted": 93}
MAIN_VALUE_AFTER_BRANCH_UPDATE = 94
SHARED_VALUE = 95
MIGRATED_COPY_VALUE = 99
SET_BACK_MAIN_DETOUR = 96
SET_BACK_BRANCH_MAIN_VALUE = 97
SET_BACK_BRANCH_DETOUR = 98


@dataclass(frozen=True)
class PoolFigures:
    """Everything a pool reports about itself, in a form the two eras can be compared in."""

    utilization: float
    utilization_default_branch: float
    utilization_branches: float

    allocated: tuple[tuple[str, int], ...]
    """The branch split: one (branch, number) pair per allocation the pool accounts for."""

    in_use: tuple[int, ...]


# -----------------------------------------------------------------------------------------------
# The pre-change readers
# -----------------------------------------------------------------------------------------------

# The pre-change IS_RESERVED pointed at the shared `AttributeValue` vertex, named its object in the record's
# `identifier`, and relied on a stored `HAS_SOURCE` edge to say which pool an allocation belonged to.
# Both readers are reproduced verbatim from that era, because a database an upgrade has not yet
# touched is the only thing a "before" figure can be taken from.

_LEGACY_ALLOCATED = """
MATCH (n:%(node)s)-[ha:HAS_ATTRIBUTE]-(a:Attribute {name: $node_attribute})-[hv:HAS_VALUE]-(av:AttributeValueIndexed)
MATCH (a)-[hs:HAS_SOURCE]-(pool:%(number_pool)s)-[ir:IS_RESERVED]->(av)
CALL (a, pool) {
    MATCH (a)-[hs_int:HAS_SOURCE]->(pool)
    WHERE hs_int.status = "active"
        AND hs_int.to IS NULL
        AND NOT EXISTS {
            MATCH (a)-[hs_deleted:HAS_SOURCE {branch: hs_int.branch, status: "deleted"}]->(pool)
            WHERE hs_deleted.from > hs_int.from
        }
    RETURN true AS hs_active
    LIMIT 1
}
WITH n, ha, a, hv, av, hs, pool, ir, hs_active
WHERE
    hs_active = TRUE
    AND pool.uuid = $pool_id
    AND av.value >= $start_range and av.value <= $end_range
    AND all(r in [ha, hv, hs] WHERE (%(branch_filter)s))
    AND ha.status = "active"
    AND hv.status = "active"
RETURN DISTINCT n.uuid AS id, hv.branch AS branch, av.value AS value
ORDER BY av.value
"""

_LEGACY_USED = """
MATCH (pool:%(number_pool)s { uuid: $pool_id })-[res:IS_RESERVED]->(av:AttributeValueIndexed)
WHERE toInteger(av.value) >= $start_range and toInteger(av.value) <= $end_range
CALL (pool, res, av) {
    MATCH (pool)-[res]->(av)<-[hv:HAS_VALUE]-(attr:Attribute)<-[ha:HAS_ATTRIBUTE]-(n:%(node)s)
    WHERE
        n.uuid = res.identifier AND
        attr.name = $attribute_name AND
        all(r in [res, hv, ha] WHERE (%(branch_filter)s))
    ORDER BY res.branch_level DESC, hv.branch_level DESC, ha.branch_level DESC,
        res.from DESC, hv.from DESC, ha.from DESC,
        res.status ASC, hv.status ASC, ha.status ASC
    RETURN (res.status = "active" AND hv.status = "active" AND ha.status = "active") AS is_active
    LIMIT 1
}
WITH av, res, is_active
WHERE is_active = True
RETURN DISTINCT(av.value) AS value
ORDER BY value
"""


async def legacy_figures(db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch) -> PoolFigures:
    """What the pool reported before the ledger moved."""
    at = Timestamp()
    branch_filter, branch_params = branch.get_query_filter_path(at=at.to_string(), branch_agnostic=True)
    params: dict[str, Any] = {
        "pool_id": pool.get_id(),
        "node_attribute": TRACKED_ATTRIBUTE_NAME,
        "attribute_name": TRACKED_ATTRIBUTE_NAME,
        "start_range": POOL_START,
        "end_range": POOL_END,
        **branch_params,
    }
    substitutions = {
        "node": TICKET.kind,
        "number_pool": InfrahubKind.NUMBERPOOL,
        "branch_filter": branch_filter,
    }

    allocated_results = await db.execute_query(query=_LEGACY_ALLOCATED % substitutions, params=params)
    used_results = await db.execute_query(query=_LEGACY_USED % substitutions, params=params)

    allocated = [(str(result["branch"]), int(result["value"])) for result in allocated_results]

    # The arithmetic the utilization getter does on the rows it reads, applied to the rows the
    # pre-change reader returned.
    used_default = {value for row_branch, value in allocated if row_branch == registry.default_branch}
    used_branches = {value for row_branch, value in allocated if row_branch != registry.default_branch} - used_default
    total = POOL_END - POOL_START + 1 - pool.get_attribute_nb_excluded_values()

    return PoolFigures(
        utilization=((len(used_branches) + len(used_default)) / total) * 100,
        utilization_default_branch=(len(used_default) / total) * 100,
        utilization_branches=(len(used_branches) / total) * 100,
        allocated=tuple(sorted(allocated)),
        in_use=tuple(sorted(int(result["value"]) for result in used_results)),
    )


async def current_figures(db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch) -> PoolFigures:
    """What the pool reports now, through the readers that target the attribute."""
    getter = NumberUtilizationGetter(db=db, pool=pool, branch=branch)
    await getter.load_data()

    return PoolFigures(
        utilization=getter.utilization,
        utilization_default_branch=getter.utilization_default_branch,
        utilization_branches=getter.utilization_branches,
        allocated=tuple(sorted((entry.branch, entry.number) for entry in getter.used)),
        in_use=tuple(sorted(await pool.get_used(db=db, branch=branch))),
    )


def carried(properties: dict[str, Any]) -> dict[str, Any]:
    """The properties whose survival across the move is what makes the record still readable."""
    return {name: properties.get(name) for name in CARRIED_PROPERTIES}


@dataclass
class MigratedDatabase:
    default_branch: Branch
    pools: dict[str, CoreNumberPool]
    tickets: dict[str, Node]

    attribute_ids: dict[str, str]
    """Each ticket's tracked attribute, read before any second `Node` vertex was added on its uuid."""

    moved_record_before: ReservationRecord

    earliest_from: dict[str, str]
    """The earliest `from` among each ticket's legacy records, read before the migration."""

    figures_before: dict[str, PoolFigures]
    first_run: MigrationRun
    records_after_first_run: list[ReservationRecord]
    second_run: MigrationRun


class TestMigration080:
    @pytest.fixture(scope="class")
    async def migrated(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema_scope_class: None
    ) -> MigratedDatabase:
        default_branch = default_branch_scope_class
        # alpha and beta carry the cases whose pool figures are compared across the upgrade, so they
        # allocate first and their numbers are known.
        pools = {
            name: await create_pool(db=db, name=name)
            for name in ("alpha", "beta", "gamma", "converted", "retired", "repool_a", "repool_b")
        }

        # migrated_copy is the only ticket the kind-change branch can see, so the kind migration
        # only affexts this object.
        tickets: dict[str, Node] = {
            "migrated_copy": await create_ticket_with_value(db=db, title="migrated_copy", value=MIGRATED_COPY_VALUE)
        }
        await create_legacy_record(db=db, pool_id=pools["gamma"].id, node_id=tickets["migrated_copy"].id)
        kind_change = await create_branch(db=db, branch_name="kind-change")
        kind_migration = await migrate_ticket_inheritance(db=db, branch=kind_change)
        assert kind_migration.errors == []
        assert kind_migration.nbr_migrations_executed == 1

        for name, pool in (
            ("on_main_a", "alpha"),
            ("on_main_b", "alpha"),
            ("re_pooled", "alpha"),
            ("deleted_on_branch", "alpha"),
            ("from_beta", "beta"),
            ("attribute_gone", "alpha"),
            ("moved", "gamma"),
            ("deleted", "gamma"),
            ("deleted_after_branching", "gamma"),
            ("updated", "gamma"),
            ("updated_after_branching", "gamma"),
            ("duplicated", "gamma"),
            ("same_moment", "gamma"),
            ("converted_from", "converted"),
            ("retired", "retired"),
            ("branch_updated_main_updated", "gamma"),
            ("branch_updated_main_deleted", "gamma"),
            ("set_back_main", "gamma"),
            ("set_back_branch", "gamma"),
            ("repooled_on_main_after_branching", "repool_a"),
            ("repooled_on_branch", "repool_a"),
        ):
            tickets[name] = await create_ticket(db=db, title=name, pool=pools[pool])
        tickets["allocated_on_update"] = await create_ticket_allocated_on_update(
            db=db, title="allocated_on_update", pool=pools["gamma"]
        )
        attribute_ids = {name: attribute_id_of(node=ticket) for name, ticket in tickets.items()}

        # The pre-upgrade code reserved before the attribute existed on create, and after it on update.
        created = [
            ticket.id for name, ticket in tickets.items() if name not in {"allocated_on_update", "migrated_copy"}
        ]
        assert await rewrite_records_to_legacy_shape(db=db, node_ids=created) == len(created)
        assert (
            await rewrite_records_to_legacy_shape(
                db=db, node_ids=[tickets["allocated_on_update"].id], backdate_seconds=0
            )
            == 1
        )

        # re_pooled: a second pool claimed the object without the first pool's record being ended,
        # and both pools stored themselves as its source.
        await create_legacy_record(
            db=db, pool_id=pools["beta"].id, node_id=tickets["re_pooled"].id, at=Timestamp().subtract(seconds=60)
        )
        await create_legacy_record(
            db=db, pool_id=pools["alpha"].id, node_id=tickets["on_main_a"].id, identifier=ORPHAN_IDENTIFIER
        )
        for name, pool in (
            ("on_main_a", "alpha"),
            ("on_main_b", "alpha"),
            ("re_pooled", "alpha"),
            ("re_pooled", "beta"),
            ("deleted_on_branch", "alpha"),
            ("from_beta", "beta"),
            ("attribute_gone", "alpha"),
            ("converted_from", "converted"),
        ):
            await create_legacy_source_edge(
                db=db, node_id=tickets[name].id, pool_id=pools[pool].id, branch=default_branch
            )

        await create_legacy_record(
            db=db, pool_id=pools["gamma"].id, node_id=tickets["duplicated"].id, at=Timestamp().subtract(seconds=600)
        )
        await create_legacy_record(
            db=db, pool_id=pools["gamma"].id, node_id=tickets["duplicated"].id, at=Timestamp().subtract(seconds=60)
        )
        shared_moment = Timestamp().subtract(seconds=60)
        for _ in range(2):
            await create_legacy_record(
                db=db, pool_id=pools["gamma"].id, node_id=tickets["same_moment"].id, at=shared_moment
            )

        # shared_dead held the shared number with a record of its own, then was deleted.
        tickets["shared_dead"] = await create_ticket_with_value(db=db, title="shared_dead", value=SHARED_VALUE)
        attribute_ids["shared_dead"] = attribute_id_of(node=tickets["shared_dead"])
        await create_legacy_record(db=db, pool_id=pools["gamma"].id, node_id=tickets["shared_dead"].id)
        shared_dead = await NodeManager.get_one(db=db, id=tickets["shared_dead"].id, raise_on_error=True)
        await shared_dead.delete(db=db)

        set_back_number = tickets["set_back_main"].get_attribute(name=TRACKED_ATTRIBUTE_NAME).value
        assert isinstance(set_back_number, int)
        await update_tracked_value(db=db, node_id=tickets["set_back_main"].id, value=SET_BACK_MAIN_DETOUR)
        await update_tracked_value(db=db, node_id=tickets["set_back_main"].id, value=set_back_number)

        # These objects are only visible on the default branch.
        # The data removed is not readable from any other branch.
        deleted = await NodeManager.get_one(db=db, id=tickets["deleted"].id, raise_on_error=True)
        await deleted.delete(db=db)
        await update_tracked_value(db=db, node_id=tickets["updated"].id, value=UPDATED_VALUE)
        await pools["retired"].delete(db=db)
        # Conversion deletes the object and re-creates it under a new uuid holding the same number.
        converted_number = tickets["converted_from"].get_attribute(name=TRACKED_ATTRIBUTE_NAME).value
        assert isinstance(converted_number, int)
        converted_from = await NodeManager.get_one(db=db, id=tickets["converted_from"].id, raise_on_error=True)
        await converted_from.delete(db=db)
        tickets["converted_to"] = await create_ticket_with_value(db=db, title="converted_to", value=converted_number)
        attribute_ids["converted_to"] = attribute_id_of(node=tickets["converted_to"])
        assert (
            await convert_legacy_records(
                db=db, from_node_id=tickets["converted_from"].id, to_node_id=tickets["converted_to"].id
            )
            == 1
        )

        feature = await create_branch(db=db, branch_name="feature")
        tickets["on_feature"] = await create_ticket(db=db, title="on_feature", pool=pools["alpha"], branch=feature)
        attribute_ids["on_feature"] = attribute_id_of(node=tickets["on_feature"])
        assert await rewrite_records_to_legacy_shape(db=db, node_ids=[tickets["on_feature"].id]) == 1
        await create_legacy_source_edge(
            db=db, node_id=tickets["on_feature"].id, pool_id=pools["alpha"].id, branch=feature
        )
        on_feature_branch = await NodeManager.get_one(
            db=db, id=tickets["deleted_on_branch"].id, branch=feature, raise_on_error=True
        )
        await on_feature_branch.delete(db=db)

        # The branch moves off the reserved number, then main moves off it too, before any later branch
        # is created that could still read it.
        for name, value in BRANCH_VALUES.items():
            await update_tracked_value(db=db, node_id=tickets[name].id, value=value, branch=feature)
        await update_tracked_value(
            db=db, node_id=tickets["branch_updated_main_updated"].id, value=MAIN_VALUE_AFTER_BRANCH_UPDATE
        )
        branch_updated_main_deleted = await NodeManager.get_one(
            db=db, id=tickets["branch_updated_main_deleted"].id, raise_on_error=True
        )
        await branch_updated_main_deleted.delete(db=db)

        await rename_tracked_attribute(db=db, node_id=tickets["attribute_gone"].id, new_name=RENAMED_ATTRIBUTE_NAME)

        # shared_owner reserved the shared number on main after shared_dead let it go, and
        # shared_hand_set holds the same number by hand on a branch that never saw shared_owner.
        tickets["shared_owner"] = await create_ticket_with_value(db=db, title="shared_owner", value=SHARED_VALUE)
        await create_legacy_record(db=db, pool_id=pools["gamma"].id, node_id=tickets["shared_owner"].id)
        tickets["shared_hand_set"] = await create_ticket_with_value(
            db=db, title="shared_hand_set", value=SHARED_VALUE, branch=feature
        )
        for name in ("shared_owner", "shared_hand_set"):
            attribute_ids[name] = attribute_id_of(node=tickets[name])

        # Main moves off the number for good; the branch leaves it and comes back.
        set_back_branch_number = tickets["set_back_branch"].get_attribute(name=TRACKED_ATTRIBUTE_NAME).value
        assert isinstance(set_back_branch_number, int)
        await update_tracked_value(db=db, node_id=tickets["set_back_branch"].id, value=SET_BACK_BRANCH_MAIN_VALUE)
        await update_tracked_value(
            db=db, node_id=tickets["set_back_branch"].id, value=SET_BACK_BRANCH_DETOUR, branch=feature
        )
        await update_tracked_value(
            db=db, node_id=tickets["set_back_branch"].id, value=set_back_branch_number, branch=feature
        )

        # A second pool claims each object while the first pool's number stays readable on another branch.
        await allocate_from_pool(db=db, node_id=tickets["repooled_on_main_after_branching"].id, pool=pools["repool_b"])
        await allocate_from_pool(
            db=db, node_id=tickets["repooled_on_branch"].id, pool=pools["repool_b"], branch=feature
        )
        for name in ("repooled_on_main_after_branching", "repooled_on_branch"):
            assert await rewrite_records_to_legacy_shape(db=db, node_ids=[tickets[name].id]) == 1

        # feature was created before these, so it still reads the object and its old value.
        deleted_after_branching = await NodeManager.get_one(
            db=db, id=tickets["deleted_after_branching"].id, raise_on_error=True
        )
        await deleted_after_branching.delete(db=db)
        await update_tracked_value(
            db=db, node_id=tickets["updated_after_branching"].id, value=UPDATED_AFTER_BRANCHING_VALUE
        )

        # The only copy lives on a branch that is being deleted.
        doomed_branch = await create_branch(db=db, branch_name="doomed")
        tickets["doomed"] = await create_ticket(db=db, title="doomed", pool=pools["gamma"], branch=doomed_branch)
        attribute_ids["doomed"] = attribute_id_of(node=tickets["doomed"])
        assert await rewrite_records_to_legacy_shape(db=db, node_ids=[tickets["doomed"].id]) == 1
        await set_branch_status(db=db, branch_name=doomed_branch.name, status="DELETING")

        legacy_open = {
            record.properties["identifier"]
            for record in await reservation_records(db=db)
            if record.anchor == "AttributeValue" and record.properties.get("to") is None
        }
        for name in (
            "deleted",
            "deleted_after_branching",
            "updated",
            "updated_after_branching",
            "deleted_on_branch",
            "branch_updated_main_updated",
            "branch_updated_main_deleted",
            "shared_dead",
            "shared_owner",
            "set_back_main",
            "set_back_branch",
            "repooled_on_main_after_branching",
            "repooled_on_branch",
            "doomed",
            "converted_to",
            "migrated_copy",
        ):
            assert tickets[name].id in legacy_open, f"the {name} fixture must leave its legacy record open"

        moved_record_before = next(
            record
            for record in await reservation_records(db=db, pool_id=pools["gamma"].id)
            if record.properties["identifier"] == tickets["moved"].id
        )
        earliest_from = {
            name: min(
                record.properties["from"]
                for record in await reservation_records(db=db)
                if record.properties["identifier"] == tickets[name].id
            )
            for name in ("re_pooled", "duplicated", "repooled_on_main_after_branching", "repooled_on_branch")
        }
        figures_before = {
            name: await legacy_figures(db=db, pool=pools[name], branch=default_branch) for name in ("alpha", "beta")
        }

        first_run = await run_migration(db=db)
        records_after_first_run = await reservation_records(db=db)
        second_run = await run_migration(db=db)

        return MigratedDatabase(
            default_branch=default_branch,
            pools=pools,
            tickets=tickets,
            attribute_ids=attribute_ids,
            moved_record_before=moved_record_before,
            earliest_from=earliest_from,
            figures_before=figures_before,
            first_run=first_run,
            records_after_first_run=records_after_first_run,
            second_run=second_run,
        )

    @staticmethod
    async def records_for(db: InfrahubDatabase, migrated: MigratedDatabase, ticket: str) -> list[ReservationRecord]:
        identifier = migrated.tickets[ticket].id
        return [record for record in await reservation_records(db=db) if record.properties["identifier"] == identifier]

    async def test_first_run_reports_every_behaviour_and_validates(self, migrated: MigratedDatabase) -> None:
        run = migrated.first_run
        assert not run.result.errors
        assert not run.validation.errors
        assert "Re-anchored 26 number pool record(s) onto the attribute they belong to." in run.output
        # Nine legacy source edges, plus the deleted-status ones written by deleting two objects that had one.
        assert "Deleted 11 stored source edge(s) naming a number pool." in run.output
        assert "Dropped 7 number pool record(s) an attribute held beyond the newest one." in run.output
        assert "Dropped 10 number pool record(s) that no longer reserved a number on any branch." in run.output
        assert run.result.nbr_migrations_executed == 54

    async def test_second_run_finds_nothing_left_to_do(self, db: InfrahubDatabase, migrated: MigratedDatabase) -> None:
        run = migrated.second_run
        assert not run.result.errors
        assert not run.validation.errors
        assert run.result.nbr_migrations_executed == 0
        assert "Re-anchored 0 number pool record(s) onto the attribute they belong to." in run.output
        assert "Deleted 0 stored source edge(s) naming a number pool." in run.output
        assert "Dropped 0 number pool record(s) an attribute held beyond the newest one." in run.output
        assert "Dropped 0 number pool record(s) that no longer reserved a number on any branch." in run.output

        def ordered(records: list[ReservationRecord]) -> list[ReservationRecord]:
            return sorted(
                records, key=lambda record: (record.attribute_id or "", record.pool_id, str(record.properties))
            )

        assert ordered(await reservation_records(db=db)) == ordered(migrated.records_after_first_run)

    async def test_a_legacy_record_moves_onto_the_attribute_with_its_properties(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        before = migrated.moved_record_before
        assert before.anchor == "AttributeValue"
        assert "provenance" not in before.properties

        after = await self.records_for(db=db, migrated=migrated, ticket="moved")
        assert len(after) == 1
        assert after[0].anchor == "Attribute"
        assert after[0].attribute_id == migrated.attribute_ids["moved"]
        assert carried(after[0].properties) == carried(before.properties)
        assert "provenance" not in after[0].properties, "an absent provenance already reads as allocated"

    async def test_a_record_reserved_after_its_attribute_existed_moves(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        after = await self.records_for(db=db, migrated=migrated, ticket="allocated_on_update")
        assert [(record.anchor, record.attribute_id) for record in live_records(after)] == [
            ("Attribute", migrated.attribute_ids["allocated_on_update"])
        ]

    async def test_a_shared_value_vertex_gives_a_record_only_to_the_object_that_reserved_it(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        """Value vertices are shared by every attribute holding the number, so the record is resolved by identity."""
        assert [
            (record.pool_id, record.attribute_id)
            for record in live_records(await self.records_for(db=db, migrated=migrated, ticket="shared_owner"))
        ] == [(migrated.pools["gamma"].id, migrated.attribute_ids["shared_owner"])]
        assert (
            await reservation_records_on_attribute(db=db, attribute_id=migrated.attribute_ids["shared_hand_set"]) == []
        )
        assert await self.records_for(db=db, migrated=migrated, ticket="shared_dead") == []

    @pytest.mark.parametrize("ticket", ["set_back_main", "set_back_branch"])
    async def test_a_value_set_back_to_the_reserved_number_keeps_its_record(
        self, db: InfrahubDatabase, migrated: MigratedDatabase, ticket: str
    ) -> None:
        after = await self.records_for(db=db, migrated=migrated, ticket=ticket)
        assert [(record.anchor, record.attribute_id) for record in live_records(after)] == [
            ("Attribute", migrated.attribute_ids[ticket])
        ]

    @pytest.mark.parametrize("ticket", ["repooled_on_main_after_branching", "repooled_on_branch"])
    async def test_a_repool_held_through_different_branches_keeps_the_newest_pool_with_the_earliest_from(
        self, db: InfrahubDatabase, migrated: MigratedDatabase, ticket: str
    ) -> None:
        after = live_records(await self.records_for(db=db, migrated=migrated, ticket=ticket))
        assert [(record.pool_id, record.attribute_id) for record in after] == [
            (migrated.pools["repool_b"].id, migrated.attribute_ids[ticket])
        ]
        assert after[0].properties["from"] == migrated.earliest_from[ticket]

    async def test_a_record_held_only_by_a_deleting_branch_is_dropped(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        assert await self.records_for(db=db, migrated=migrated, ticket="doomed") == []

    async def test_node_vertices_sharing_a_uuid_and_attribute_get_one_record(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        """A kind migration copies the `Node` vertex but both vertices own the original `Attribute`."""
        owners = await db.execute_query(
            query="""
            MATCH (node:Node { uuid: $node_id })-[:HAS_ATTRIBUTE]->(attr:Attribute { uuid: $attribute_id })
            RETURN count(DISTINCT node) AS node_vertices
            """,
            params={
                "node_id": migrated.tickets["migrated_copy"].id,
                "attribute_id": migrated.attribute_ids["migrated_copy"],
            },
        )
        assert owners[0]["node_vertices"] == 2, "the kind migration must leave two Node vertices owning the attribute"
        after = await self.records_for(db=db, migrated=migrated, ticket="migrated_copy")
        assert [(record.anchor, record.attribute_id) for record in live_records(after)] == [
            ("Attribute", migrated.attribute_ids["migrated_copy"])
        ]
        assert len(after) == 1

    async def test_a_record_naming_no_object_is_dropped(self, db: InfrahubDatabase) -> None:
        records = await reservation_records(db=db)
        assert [record for record in records if record.properties["identifier"] == ORPHAN_IDENTIFIER] == []

    async def test_a_record_whose_object_was_deleted_before_any_branch_is_dropped(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        assert await self.records_for(db=db, migrated=migrated, ticket="deleted") == []

    async def test_a_record_whose_value_was_updated_before_any_branch_is_dropped(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        assert await self.records_for(db=db, migrated=migrated, ticket="updated") == []

    @pytest.mark.parametrize("ticket", ["branch_updated_main_updated", "branch_updated_main_deleted"])
    async def test_a_record_is_dropped_once_both_main_and_the_branch_moved_off_the_number(
        self, db: InfrahubDatabase, migrated: MigratedDatabase, ticket: str
    ) -> None:
        """The branch set its own value before main changed or deleted the object, so no branch reads the number."""
        assert await self.records_for(db=db, migrated=migrated, ticket=ticket) == []
        assert await reservation_records_on_attribute(db=db, attribute_id=migrated.attribute_ids[ticket]) == []

    async def test_a_record_survives_a_delete_an_older_branch_has_not_seen(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        after = await self.records_for(db=db, migrated=migrated, ticket="deleted_after_branching")
        assert [(record.anchor, record.attribute_id) for record in live_records(after)] == [
            ("Attribute", migrated.attribute_ids["deleted_after_branching"])
        ]

    async def test_a_record_survives_an_update_an_older_branch_has_not_seen(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        after = await self.records_for(db=db, migrated=migrated, ticket="updated_after_branching")
        assert [(record.anchor, record.attribute_id) for record in live_records(after)] == [
            ("Attribute", migrated.attribute_ids["updated_after_branching"])
        ]

    async def test_a_record_survives_an_object_deleted_on_one_branch_only(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        after = await self.records_for(db=db, migrated=migrated, ticket="deleted_on_branch")
        assert [(record.anchor, record.attribute_id) for record in live_records(after)] == [
            ("Attribute", migrated.attribute_ids["deleted_on_branch"])
        ]

    async def test_a_record_naming_an_attribute_its_object_lacks_is_dropped(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        assert await self.records_for(db=db, migrated=migrated, ticket="attribute_gone") == []

    async def test_a_record_of_a_deleted_pool_is_dropped(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        assert await reservation_records(db=db, pool_id=migrated.pools["retired"].id) == []

    async def test_a_converted_objects_record_moves_to_the_object_it_became(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        """Conversion closed the old object's record and opened one naming the new object."""
        assert await self.records_for(db=db, migrated=migrated, ticket="converted_from") == []
        assert [
            (record.pool_id, record.attribute_id)
            for record in live_records(await self.records_for(db=db, migrated=migrated, ticket="converted_to"))
        ] == [(migrated.pools["converted"].id, migrated.attribute_ids["converted_to"])]

    async def test_the_newest_claim_survives_when_two_pools_hold_one_object(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        after = live_records(await self.records_for(db=db, migrated=migrated, ticket="re_pooled"))
        assert [(record.pool_id, record.attribute_id) for record in after] == [
            (migrated.pools["beta"].id, migrated.attribute_ids["re_pooled"])
        ]
        assert after[0].properties["from"] == migrated.earliest_from["re_pooled"], (
            "the attribute has been reserved since its earliest claim"
        )

    async def test_one_record_survives_one_pools_duplicates_with_the_earliest_from(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        after = live_records(await self.records_for(db=db, migrated=migrated, ticket="duplicated"))
        assert len(after) == 1
        assert after[0].properties["from"] == migrated.earliest_from["duplicated"]

    async def test_records_sharing_a_timestamp_leave_no_duplicate_path(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        """Graph validation cannot tell apart two same-pool records with one `from` on one anchor."""
        assert len(live_records(await self.records_for(db=db, migrated=migrated, ticket="same_moment"))) == 1

        violations = await collect_graph_violations(db=db)
        assert [
            violation.message
            for violation in violations
            if violation.check == GraphCheck.DUPLICATE_PATHS and "IS_RESERVED" in violation.message
        ] == []

    async def test_no_number_pool_is_left_stored_as_a_source(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        """Covers a live record, a collapsed-away one, a converted one, and one with no attribute to move to."""
        for name in ("on_main_a", "re_pooled", "converted_from"):
            assert await stored_source_pool_ids(db=db, node_id=migrated.tickets[name].id) == [], name
        assert (
            await stored_source_pool_ids(
                db=db, node_id=migrated.tickets["attribute_gone"].id, attribute_name=RENAMED_ATTRIBUTE_NAME
            )
            == []
        )

    async def test_every_figure_a_pool_reports_survives_the_re_anchoring(
        self, db: InfrahubDatabase, migrated: MigratedDatabase
    ) -> None:
        tickets = migrated.tickets
        default_branch = migrated.default_branch

        # Pinned so a change in allocation order fails here rather than rewriting what the figures mean.
        numbers = {
            name: tickets[name].get_attribute(name=TRACKED_ATTRIBUTE_NAME).value
            for name in (
                "on_main_a",
                "on_main_b",
                "re_pooled",
                "deleted_on_branch",
                "from_beta",
                "attribute_gone",
                "on_feature",
            )
        }
        assert numbers == {
            "on_main_a": 1,
            "on_main_b": 2,
            "re_pooled": 3,
            "deleted_on_branch": 4,
            "from_beta": 5,
            "attribute_gone": 6,
            "on_feature": 8,
        }

        before = migrated.figures_before
        after = {
            name: await current_figures(db=db, pool=migrated.pools[name], branch=default_branch)
            for name in ("alpha", "beta")
        }

        assert after["beta"] == before["beta"], "nothing the second pool reports may move"

        # alpha moves in exactly two places, and both are corrections:
        # - it stops reporting 3, which belongs to beta since the object was re-pooled;
        # - it starts reporting 4 in use, because the default branch still holds that object.
        assert before["alpha"] == PoolFigures(
            utilization=5.0,
            utilization_default_branch=4.0,
            utilization_branches=1.0,
            allocated=(("feature", 8), ("main", 1), ("main", 2), ("main", 3), ("main", 4)),
            in_use=(1, 2, 3, 8),
        )
        assert after["alpha"] == PoolFigures(
            utilization=4.0,
            utilization_default_branch=3.0,
            utilization_branches=1.0,
            allocated=(("feature", 8), ("main", 1), ("main", 2), ("main", 4)),
            in_use=(1, 2, 4, 8),
        )

        # The record naming an attribute its object no longer carries releases nothing: neither era
        # ever reported 6.
        for figures in (before["alpha"], after["alpha"]):
            assert 6 not in figures.in_use
            assert 6 not in {number for _, number in figures.allocated}
