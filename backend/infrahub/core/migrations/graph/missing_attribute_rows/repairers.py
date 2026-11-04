from __future__ import annotations

from dataclasses import dataclass
from itertools import batched
from typing import TYPE_CHECKING, Protocol

from infrahub.core.manager import NodeManager
from infrahub.core.migrations.query.attribute_add import AttributeAddQuery
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.pools.existing_node_numbers import build_existing_node_number_allocator

if TYPE_CHECKING:
    from rich.console import Console

    from infrahub.core.branch import Branch
    from infrahub.core.schema import NodeSchema
    from infrahub.core.schema.attribute_schema import AttributeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter

NUMBER_POOL_ATTRIBUTE_KIND = "NumberPool"


@dataclass(frozen=True)
class MissingRows:
    """The damaged (active node, inherited attribute) pairs of one attribute of one kind on one branch."""

    branch: Branch
    node_schema: NodeSchema
    attribute: AttributeSchema
    node_kinds: list[str]
    node_uuids: set[str]
    at: Timestamp
    user_id: str


class MissingRowRepairer(Protocol):
    """Creates the rows one family of attributes is missing."""

    def supports(self, attribute: AttributeSchema) -> bool: ...

    async def repair(self, rows: MissingRows) -> int: ...


class DefaultValueRowRepairer:
    """Create missing rows carrying the schema default, a null value when the attribute has none.

    Writes are chunked so a large repair neither exceeds the database's transaction memory
    limits nor runs silently; each chunk is one atomic auto-committed statement, and a rerun
    after a partial failure converges through the query's idempotency.
    """

    def __init__(self, db: InfrahubDatabase, console: Console, batch_size: int) -> None:
        self.db = db
        self.console = console
        self.batch_size = batch_size

    def supports(self, attribute: AttributeSchema) -> bool:
        return attribute.kind != NUMBER_POOL_ATTRIBUTE_KIND

    async def repair(self, rows: MissingRows) -> int:
        label = f"{rows.node_schema.kind}.{rows.attribute.name}"
        # sorted for deterministic chunk composition and reproducible logs
        multiple_batches = len(rows.node_uuids) > self.batch_size
        created = 0
        for uuid_batch in batched(sorted(rows.node_uuids), self.batch_size):
            query = await AttributeAddQuery.init(
                db=self.db,
                branch=rows.branch,
                at=rows.at,
                user_id=rows.user_id,
                node_kinds=rows.node_kinds,
                attribute_name=rows.attribute.name,
                attribute_kind=rows.attribute.kind,
                branch_support=rows.attribute.get_branch().value,
                default_value=rows.attribute.default_value,
                uuids=list(uuid_batch),
            )
            await query.execute(db=self.db)
            created += query.num_of_results
            if multiple_batches:
                self.console.log(f"    {label}: created {created}/{len(rows.node_uuids)} row(s)")

        self.console.log(f"    {label}: created {created} row(s)")
        return created


class PoolBackedRowRepairer:
    """Create missing rows with a value allocated per node from the attribute's number pool, within the node's division.

    The pool is upserted the same way the schema change that introduces the attribute
    provisions it, so a damaged install missing the pool is healed rather than failed. Work
    is chunked: within a chunk, allocation and row write are interleaved per node inside one
    transaction, so every allocation sees the reservations of the previous ones; committed
    chunks survive a later failure, and allocations are reservation-aware, so healthy nodes
    and reruns never re-allocate. Pool exhaustion aborts the current chunk and surfaces as a
    per-attribute error.
    """

    def __init__(
        self, db: InfrahubDatabase, console: Console, batch_size: int, upserter: SchemaNumberPoolUpserter
    ) -> None:
        self.db = db
        self.console = console
        self.batch_size = batch_size
        self.upserter = upserter

    def supports(self, attribute: AttributeSchema) -> bool:
        return attribute.kind == NUMBER_POOL_ATTRIBUTE_KIND

    async def repair(self, rows: MissingRows) -> int:
        """Allocate and write one value per damaged node; return the number repaired.

        Raises:
            TypeError: When the upserted pool is not an allocation-capable pool node.
            ValidationError: When the pool's scope or a node's division cannot be read.
            NodeNotFoundError: When a scope peer named by a human-friendly id or a default filter value does not exist.
            PoolExhaustedError: When the pool, or a node's division, has no number left to give.

        """
        label = f"{rows.node_schema.kind}.{rows.attribute.name}"
        number_pool = await self.upserter.upsert_number_pool(
            schema_node=rows.node_schema,
            attribute=rows.attribute,
            branch_name=rows.branch.name,
            at=rows.at,
            user_id=rows.user_id,
        )
        if not isinstance(number_pool, CoreNumberPool):
            raise TypeError(f"expected a number pool node for {label}")

        # sorted for deterministic chunk composition, allocation order, and reproducible logs
        multiple_batches = len(rows.node_uuids) > self.batch_size
        repaired = 0
        for uuid_batch in batched(sorted(rows.node_uuids), self.batch_size):
            async with self.db.start_transaction() as dbt:
                query = await AttributeAddQuery.init(
                    db=dbt,
                    branch=rows.branch,
                    at=rows.at,
                    user_id=rows.user_id,
                    node_kinds=rows.node_kinds,
                    attribute_name=rows.attribute.name,
                    attribute_kind=rows.attribute.kind,
                    branch_support=rows.attribute.get_branch().value,
                    default_value=None,
                    uuids=list(uuid_batch),
                )
                await query.execute(db=dbt)

                allocator = build_existing_node_number_allocator(db=dbt, branch=rows.branch)
                nodes = await NodeManager.get_many(db=dbt, branch=rows.branch, ids=list(uuid_batch))
                # Counted per allocated node rather than from the rows the query created.
                repaired += await allocator.allocate(
                    pool=number_pool,
                    attribute=rows.attribute,
                    nodes=[nodes[node_uuid] for node_uuid in sorted(nodes)],
                    branch=rows.branch,
                    at=rows.at,
                    user_id=rows.user_id,
                )
            if multiple_batches:
                self.console.log(f"    {label}: allocated {repaired}/{len(rows.node_uuids)} pool value(s)")

        self.console.log(f"    {label}: allocated {repaired} pool value(s)")
        return repaired
