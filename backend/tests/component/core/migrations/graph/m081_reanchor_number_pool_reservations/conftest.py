"""Fixtures for the number pool re-anchoring migration.

Nothing in the current code writes the shape this migration repairs, so the fixtures build it with
raw Cypher: a reservation record hanging off the shared `AttributeValue` vertex, naming its object
only in the record's `identifier`, and a `HAS_SOURCE` edge storing the pool as the attribute's
source. An object built by today's code is therefore *not* a subject for this migration until it has
been rewritten into that shape.

The readers report the record's anchor and its raw properties rather than a resolved pool view,
because what the migration moves is the edge itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import pytest
from rich.console import Console

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m081_reanchor_number_pool_reservations import Migration081
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.pools.attribute_pool_applier_factory import build_attribute_pool_applier
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

POOL_START = 1
POOL_END = 100
TRACKED_ATTRIBUTE_NAME = "ticket_id"
INHERITED_GENERIC = "TestingNumbered"


@dataclass(frozen=True)
class MigrationRun:
    """One run of the re-anchoring migration, with the console output it produced."""

    result: MigrationResult

    output: str
    """Everything the migration logged, so the reported counts can be asserted on."""

    validation: MigrationResult
    """What `validate_migration` found once the run had finished."""


@dataclass(frozen=True)
class ReservationRecord:
    """One `IS_RESERVED` edge, reported by what it hangs off rather than by what it means."""

    pool_id: str

    anchor: str
    """The label of the vertex the record points at: `Attribute` or `AttributeValue`."""

    attribute_id: str | None
    """The anchor's uuid when it is an `Attribute`, otherwise None."""

    properties: dict[str, Any]


async def _load_ticket_schema(db: InfrahubDatabase) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


@pytest.fixture
async def ticket_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    await _load_ticket_schema(db=db)


@pytest.fixture(scope="class")
async def ticket_schema_scope_class(
    db: InfrahubDatabase,
    default_branch_scope_class: Branch,
    register_core_models_schema_scope_class: SchemaBranch,
) -> None:
    await _load_ticket_schema(db=db)


async def create_pool(db: InfrahubDatabase, name: str) -> CoreNumberPool:
    """Build a pool tracking the ticket kind's number attribute."""
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=TICKET.kind,
        node_attribute=TRACKED_ATTRIBUTE_NAME,
        start_range=POOL_START,
        end_range=POOL_END,
    )
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=POOL_START, end=POOL_END)
    return pool


async def create_ticket(db: InfrahubDatabase, title: str, pool: CoreNumberPool, branch: Branch | None = None) -> Node:
    """Allocate a number from a pool onto a new ticket, the way today's code does."""
    ticket = await Node.init(db=db, schema=TICKET.kind, branch=branch)
    await ticket.new(db=db, title=title, ticket_id={"from_pool": {"id": pool.id}})
    await ticket.save(db=db)
    return ticket


async def run_migration(db: InfrahubDatabase, migration: Migration081 | None = None) -> MigrationRun:
    """Run the migration and keep both its console output and its own verdict on the result."""
    console = Console(record=True, width=250)
    migration = migration or Migration081()
    result = await migration.execute(migration_input=MigrationInput(db=db, console=console))
    validation = await migration.validate_migration(db=db)
    return MigrationRun(result=result, output=console.export_text(), validation=validation)


async def create_ticket_with_value(db: InfrahubDatabase, title: str, value: int, branch: Branch | None = None) -> Node:
    """Create a ticket whose number is set by hand rather than allocated from a pool."""
    ticket = await Node.init(db=db, schema=TICKET.kind, branch=branch)
    await ticket.new(db=db, title=title, ticket_id=value)
    await ticket.save(db=db)
    return ticket


async def allocate_from_pool(
    db: InfrahubDatabase, node_id: str, pool: CoreNumberPool, branch: Branch | None = None
) -> None:
    """Allocate a new number from `pool` onto an existing ticket, replacing whatever number it held."""
    ticket = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    await ticket.from_graphql(
        db=db,
        data={TRACKED_ATTRIBUTE_NAME: {"value": None, "from_pool": {"id": pool.id}}},
        pool_applier=build_attribute_pool_applier(db=db),
    )
    await ticket.save(db=db)


async def set_branch_status(db: InfrahubDatabase, branch_name: str, status: str) -> None:
    results = await db.execute_query(
        query="""
        MATCH (branch:Branch { name: $branch_name })
        SET branch.status = $status
        RETURN count(branch) AS updated
        """,
        params={"branch_name": branch_name, "status": status},
    )
    assert results[0]["updated"] == 1


async def create_ticket_allocated_on_update(db: InfrahubDatabase, title: str, pool: CoreNumberPool) -> Node:
    """Create a ticket without a number, then allocate one from the pool by updating it."""
    ticket = await Node.init(db=db, schema=TICKET.kind)
    await ticket.new(db=db, title=title)
    await ticket.save(db=db)
    await ticket.from_graphql(
        db=db,
        data={TRACKED_ATTRIBUTE_NAME: {"from_pool": {"id": pool.id}}},
        pool_applier=build_attribute_pool_applier(db=db),
    )
    await ticket.save(db=db)
    return ticket


# -----------------------------------------------------------------------------------------------
# Building the legacy shape
# -----------------------------------------------------------------------------------------------


async def rewrite_records_to_legacy_shape(
    db: InfrahubDatabase, node_ids: list[str] | None = None, backdate_seconds: int = 3600
) -> int:
    """Put every number pool record back onto the shared value vertex it used to hang off.

    The record keeps its properties bar `allocated_values`, which the pre-change writer never wrote, and is
    backdated because an upgrade finds records written well before it runs — a record stamped in the
    future is invisible to every read. This is the fixture every behaviour starts from: it turns a
    database today's code produced into the one an upgrade actually finds.

    `node_ids` limits the rewrite to those objects' records.
    """
    results = await db.execute_query(
        query="""
        MATCH (pool:%(number_pool)s)-[res:IS_RESERVED]->(attr:Attribute)
        WHERE $node_ids IS NULL OR res.identifier IN $node_ids
        // The save that reserved the number writes its value at or just after the reservation, on whichever
        // branch it ran, so that is the value the reservation was made for.
        CALL (attr, res) {
            MATCH (attr)-[hv:HAS_VALUE]->(av:AttributeValue)
            WHERE hv.status = "active" AND hv.from >= res.from
            RETURN av
            ORDER BY hv.from ASC
            LIMIT 1
        }
        CREATE (pool)-[legacy:IS_RESERVED]->(av)
        SET legacy = properties(res)
        SET legacy.from = $backdated
        REMOVE legacy.allocated_values
        DELETE res
        RETURN count(legacy) AS rewritten
        """
        % {"number_pool": InfrahubKind.NUMBERPOOL},
        params={"backdated": Timestamp().subtract(seconds=backdate_seconds).to_string(), "node_ids": node_ids},
    )
    return int(results[0]["rewritten"])


async def create_legacy_record(
    db: InfrahubDatabase,
    pool_id: str,
    node_id: str,
    identifier: str | None = None,
    at: Timestamp | None = None,
) -> None:
    """Add one more IS_RESERVED in the legacy shape, on the value vertex the object's attribute holds.

    The pre-change writer created a fresh IS_RESERVED per allocation rather than reusing one, so a single
    pool holding several IS_RESERVED edges for one object is a shape an upgrade genuinely finds.

    `identifier` defaults to the object's own uuid; passing one that names no object builds the
    orphan case.
    """
    global_branch = registry.get_global_branch()
    await db.execute_query(
        query="""
        MATCH (pool:Node:%(number_pool)s { uuid: $pool_id })
        MATCH (:Node { uuid: $node_id })-[:HAS_ATTRIBUTE]->(attr:Attribute { name: $attribute_name })
        CALL (attr) {
            MATCH (attr)-[hv:HAS_VALUE]->(av:AttributeValue)
            WHERE hv.status = "active"
            RETURN av
            ORDER BY hv.branch_level DESC, hv.from DESC
            LIMIT 1
        }
        WITH pool, av
        LIMIT 1
        CREATE (pool)-[res:IS_RESERVED]->(av)
        SET res = $properties
        """
        % {"number_pool": InfrahubKind.NUMBERPOOL},
        params={
            "pool_id": pool_id,
            "node_id": node_id,
            "attribute_name": TRACKED_ATTRIBUTE_NAME,
            "properties": {
                "branch": global_branch.name,
                "branch_level": global_branch.hierarchy_level,
                "status": "active",
                "from": (at or Timestamp()).to_string(),
                "identifier": identifier if identifier is not None else node_id,
            },
        },
    )


async def convert_legacy_records(db: InfrahubDatabase, from_node_id: str, to_node_id: str) -> int:
    """Close the object's open legacy records and open one per record for the object it was converted to.

    Object conversion was the only pre-upgrade path that closed an `IS_RESERVED` edge.
    """
    results = await db.execute_query(
        query="""
        MATCH (pool:%(number_pool)s)-[res:IS_RESERVED]->(av:AttributeValue)
        WHERE res.identifier = $from_node_id AND res.status = "active" AND res.to IS NULL
        SET res.to = $at
        CREATE (pool)-[converted:IS_RESERVED]->(av)
        SET converted = properties(res)
        SET converted.identifier = $to_node_id, converted.from = $at, converted.to = NULL
        RETURN count(converted) AS converted
        """
        % {"number_pool": InfrahubKind.NUMBERPOOL},
        params={"from_node_id": from_node_id, "to_node_id": to_node_id, "at": Timestamp().to_string()},
    )
    return int(results[0]["converted"])


async def create_legacy_source_edge(db: InfrahubDatabase, node_id: str, pool_id: str, branch: Branch) -> None:
    """Store the pool as the attribute's source, the way the pre-change writer did."""
    await db.execute_query(
        query="""
        MATCH (:Node { uuid: $node_id })-[:HAS_ATTRIBUTE]->(attr:Attribute { name: $attribute_name })
        MATCH (pool:%(number_pool)s { uuid: $pool_id })
        WITH attr, pool
        LIMIT 1
        CREATE (attr)-[:HAS_SOURCE { branch: $branch_name, branch_level: $branch_level, status: "active", from: $at }]->(pool)
        """
        % {"number_pool": InfrahubKind.NUMBERPOOL},
        params={
            "node_id": node_id,
            "attribute_name": TRACKED_ATTRIBUTE_NAME,
            "pool_id": pool_id,
            "branch_name": branch.name,
            "branch_level": branch.hierarchy_level,
            "at": Timestamp().to_string(),
        },
    )


async def migrate_ticket_inheritance(db: InfrahubDatabase, branch: Branch) -> MigrationResult:
    """Run the kind migration for an inheritance change on `branch`, copying the `Node` vertex of every ticket it sees.

    The kind is unchanged, so each copy keeps the original's `Attribute` vertices, as a real kind migration does.
    """
    previous_schema = registry.schema.get_node_schema(name=TICKET.kind, branch=branch, duplicate=False)
    new_schema = registry.schema.get_node_schema(name=TICKET.kind, branch=branch, duplicate=True)
    new_schema.inherit_from = [*new_schema.inherit_from, INHERITED_GENERIC]
    migration = NodeKindUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=new_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=new_schema.kind, field_name="inherit_from"),
    )
    return await migration.execute(migration_input=MigrationInput(db=db), branch=branch)


async def update_tracked_value(db: InfrahubDatabase, node_id: str, value: int, branch: Branch | None = None) -> None:
    """Overwrite the object's tracked number, which leaves its old reservation unread on that branch."""
    node = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    node.get_attribute(name=TRACKED_ATTRIBUTE_NAME).value = value
    await node.save(db=db)


async def rename_tracked_attribute(db: InfrahubDatabase, node_id: str, new_name: str) -> None:
    """Rename the object's attribute vertex so nothing on it answers to the name the pool tracks.

    Re-pointing a pool at another attribute, or dropping the attribute from the schema under a live
    object, leaves the same thing behind: a record naming an attribute its object does not carry.
    """
    results = await db.execute_query(
        query="""
        MATCH (:Node { uuid: $node_id })-[:HAS_ATTRIBUTE]->(attr:Attribute { name: $attribute_name })
        SET attr.name = $new_name
        RETURN count(attr) AS renamed
        """,
        params={"node_id": node_id, "attribute_name": TRACKED_ATTRIBUTE_NAME, "new_name": new_name},
    )
    assert results[0]["renamed"] > 0


# -----------------------------------------------------------------------------------------------
# Reading the graph back
# -----------------------------------------------------------------------------------------------


async def reservation_records(db: InfrahubDatabase, pool_id: str | None = None) -> list[ReservationRecord]:
    """Every `IS_RESERVED` edge a number pool holds, reported by its anchor and raw properties."""
    results = await db.execute_query(
        query="""
        MATCH (pool:%(number_pool)s)-[res:IS_RESERVED]->(target)
        WHERE $pool_id IS NULL OR pool.uuid = $pool_id
        RETURN
            pool.uuid AS pool_id,
            CASE WHEN target:Attribute THEN "Attribute" ELSE "AttributeValue" END AS anchor,
            CASE WHEN target:Attribute THEN target.uuid ELSE NULL END AS attribute_id,
            properties(res) AS properties
        """
        % {"number_pool": InfrahubKind.NUMBERPOOL},
        params={"pool_id": pool_id},
    )
    return [
        ReservationRecord(
            pool_id=result["pool_id"],
            anchor=result["anchor"],
            attribute_id=result["attribute_id"],
            properties=dict(result["properties"]),
        )
        for result in results
    ]


async def reservation_records_on_attribute(db: InfrahubDatabase, attribute_id: str) -> list[ReservationRecord]:
    """Every `IS_RESERVED` edge from any pool to the given `Attribute` vertex."""
    return [record for record in await reservation_records(db=db) if record.attribute_id == attribute_id]


def live_records(records: list[ReservationRecord]) -> list[ReservationRecord]:
    """The records a read would still resolve: active and never closed."""
    return [
        record
        for record in records
        if record.properties.get("status") == "active" and record.properties.get("to") is None
    ]


def attribute_id_of(node: Node) -> str:
    """The uuid of the object's tracked `Attribute` vertex."""
    attribute_id = node.get_attribute(name=TRACKED_ATTRIBUTE_NAME).id
    assert attribute_id is not None
    return attribute_id


async def stored_source_pool_ids(
    db: InfrahubDatabase, node_id: str, attribute_name: str = TRACKED_ATTRIBUTE_NAME
) -> list[str]:
    """The pools the object's attribute still stores as its source through a `HAS_SOURCE` edge.

    Read from the graph because a node read falls back to the reserving pool when no `HAS_SOURCE` edge is
    left, so it cannot tell a stored source from a derived one. `attribute_name` is only passed when the
    attribute has been renamed out from under the pool.
    """
    results = await db.execute_query(
        query="""
        MATCH (:Node { uuid: $node_id })-[:HAS_ATTRIBUTE]->(attr:Attribute { name: $attribute_name })
        MATCH (attr)-[source:HAS_SOURCE]->(pool:%(number_pool)s)
        WHERE source.status = "active" AND source.to IS NULL
        RETURN DISTINCT pool.uuid AS pool_id
        """
        % {"number_pool": InfrahubKind.NUMBERPOOL},
        params={"node_id": node_id, "attribute_name": attribute_name},
    )
    return sorted(result["pool_id"] for result in results)


# -----------------------------------------------------------------------------------------------
# Building one database that holds every legacy case
# -----------------------------------------------------------------------------------------------

POOL_NAMES = ("alpha", "beta", "gamma", "converted", "retired", "repool_a", "repool_b")


@dataclass(frozen=True)
class LegacyDatabase:
    pools: dict[str, CoreNumberPool]
    tickets: dict[str, Node]

    attribute_ids: dict[str, str]
    """Each ticket's tracked attribute, read before any second `Node` vertex was added on its uuid."""


class LegacyCase:
    """One legacy shape; each hook runs at its moment in the history every case shares."""

    allocated: ClassVar[tuple[tuple[str, str], ...]] = ()
    """(ticket, pool) pairs allocated by today's code, then rewritten into the legacy shape together."""

    open_legacy_records: ClassVar[tuple[str, ...]] = ()
    """The tickets whose legacy record must still be open when the migration starts."""

    earliest_from: ClassVar[tuple[str, ...]] = ()
    """The tickets whose earliest legacy `from` is read before the migration."""

    def __init__(self, db: InfrahubDatabase, default_branch: Branch, pools: dict[str, CoreNumberPool]) -> None:
        self.db = db
        self.default_branch = default_branch
        self.pools = pools
        self.tickets: dict[str, Node] = {}
        self.attribute_ids: dict[str, str] = {}

    async def before_tickets(self) -> None:
        """Runs while the database holds no ticket yet."""

    async def create_tickets(self) -> None:
        for name, pool in self.allocated:
            self.keep(name, await create_ticket(db=self.db, title=name, pool=self.pools[pool]))

    async def before_feature(self) -> None:
        """Runs once every allocated ticket is in the legacy shape, before the feature branch exists."""

    async def after_feature(self, feature: Branch) -> None:
        """Runs once the feature branch has forked from the default branch."""

    def keep(self, name: str, ticket: Node) -> None:
        self.tickets[name] = ticket
        self.attribute_ids[name] = attribute_id_of(node=ticket)

    def id(self, name: str) -> str:
        return self.tickets[name].id

    def number(self, name: str) -> int:
        """The number the ticket held when it was created."""
        value = self.tickets[name].get_attribute(name=TRACKED_ATTRIBUTE_NAME).value
        assert isinstance(value, int)
        return value

    async def legacy_source_edge(self, name: str, pool: str, branch: Branch | None = None) -> None:
        await create_legacy_source_edge(
            db=self.db, node_id=self.id(name), pool_id=self.pools[pool].id, branch=branch or self.default_branch
        )

    async def delete(self, name: str, branch: Branch | None = None) -> None:
        ticket = await NodeManager.get_one(db=self.db, id=self.id(name), branch=branch, raise_on_error=True)
        await ticket.delete(db=self.db)


class Builder:
    """Runs every case through the shared history, one step at a time across all cases."""

    def __init__(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        self.db = db
        self.default_branch = default_branch

    async def build(self, cases: list[type[LegacyCase]]) -> LegacyDatabase:
        pools = {name: await create_pool(db=self.db, name=name) for name in POOL_NAMES}
        built = [case(db=self.db, default_branch=self.default_branch, pools=pools) for case in cases]

        for case in built:
            await case.before_tickets()
        for case in built:
            await case.create_tickets()
        # The pre-upgrade code reserved before the attribute existed on create.
        created = [case.id(name) for case in built for name, _ in case.allocated]
        assert await rewrite_records_to_legacy_shape(db=self.db, node_ids=created) == len(created)

        for case in built:
            await case.before_feature()
        feature = await create_branch(db=self.db, branch_name="feature")
        for case in built:
            await case.after_feature(feature=feature)

        legacy_open = {
            record.properties["identifier"]
            for record in await reservation_records(db=self.db)
            if record.anchor == "AttributeValue" and record.properties.get("to") is None
        }
        tickets: dict[str, Node] = {}
        attribute_ids: dict[str, str] = {}
        for case in built:
            for name in case.open_legacy_records:
                assert case.id(name) in legacy_open, f"the {name} fixture must leave its legacy record open"
            shared_names = tickets.keys() & case.tickets.keys()
            assert not shared_names, f"{type(case).__name__} reuses the ticket names {sorted(shared_names)}"
            tickets |= case.tickets
            attribute_ids |= case.attribute_ids

        return LegacyDatabase(pools=pools, tickets=tickets, attribute_ids=attribute_ids)
