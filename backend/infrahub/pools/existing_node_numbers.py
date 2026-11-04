from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core import registry
from infrahub.exceptions import DivisionExhaustedError, PoolExhaustedError
from infrahub.pools.division_reader import NodeNumberPoolDivisionReader
from infrahub.pools.number_pool_number_picker import number_pool_label
from infrahub.pools.scope import AllocationScope, AllocationScopeResolver
from infrahub.profiles.data_reader import ProfileDataReader
from infrahub.profiles.node_applier import NodeProfilesApplier

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.core.schema import AttributeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.scope import Division


class DivisionReader(Protocol):
    async def read_for_pool(self, node: Node, pool: Node, attribute_name: str) -> Division | None:
        """Return the division the node holds for the number pool's scope, or None when the pool has no scope.

        Raises:
            ValidationError: When the stored scope is malformed, when the schema of the node's branch does not define
                one of its elements on the node's kind, or when an attribute element does not hold a single scalar.
            NodeNotFoundError: When a peer named by a human-friendly id or a default filter value does not exist.

        """
        ...


class ExistingNodeNumberAllocator:
    """Give existing nodes a number from a number pool, each within the division it holds as a create would."""

    def __init__(self, db: InfrahubDatabase, division_reader: DivisionReader) -> None:
        self.db = db
        self.division_reader = division_reader

    async def allocate(
        self,
        pool: CoreNumberPool,
        attribute: AttributeSchema,
        nodes: Sequence[Node],
        branch: Branch,
        at: Timestamp | None,
        user_id: str,
    ) -> int:
        """Allocate and save a number for each node, in the given order, and return how many were allocated.

        Raises:
            ValidationError: When a node's division cannot be read.
            NodeNotFoundError: When a scope peer named by a human-friendly id or a default filter value does not exist.
            PoolExhaustedError: When the pool, or a node's division, has no number left to give; for a division, the
                message adds how many of the nodes are in it and how many numbers the ranges hold.

        """
        # Every division is read before the first save, so a read failure leaves no number allocated.
        divisions = [
            await self.division_reader.read_for_pool(node=node, pool=pool, attribute_name=attribute.name)
            for node in nodes
        ]
        for node, division in zip(nodes, divisions, strict=True):
            node_attribute = node.get_attribute(name=attribute.name)
            try:
                node_attribute.value = await pool.get_resource(
                    db=self.db,
                    branch=branch,
                    identifier=node.get_id(),
                    attribute=attribute,
                    attribute_id=node_attribute.id,
                    at=at,
                    user_id=user_id,
                    division=division,
                )
            except DivisionExhaustedError as exc:
                raise PoolExhaustedError(
                    _exhausted_division_message(
                        pool=pool,
                        exc=exc,
                        node_count=divisions.count(exc.division),
                        kind=node.get_kind(),
                    )
                ) from exc
            await node.save(db=self.db, fields=[attribute.name], at=at, user_id=user_id)
        return len(nodes)


def _exhausted_division_message(pool: CoreNumberPool, exc: DivisionExhaustedError, node_count: int, kind: str) -> str:
    scope = AllocationScope.from_stored(value=pool.get_attribute("allocation_scope").value, pool=pool.get_id())
    space = "no fixed number of values" if exc.space_size is None else f"{exc.space_size} number(s)"
    return (
        f"Pool {number_pool_label(pool=pool)} has no free number left in its ranges for"
        f" {scope.describe(division=exc.division)}: {node_count} node(s) of {kind} being filled are in this division"
        f" and the ranges hold {space}."
    )


def build_existing_node_number_allocator(db: InfrahubDatabase, branch: Branch) -> ExistingNodeNumberAllocator:
    scope_resolver = AllocationScopeResolver(schema_branch=registry.schema.get_schema_branch(name=branch.name))
    return ExistingNodeNumberAllocator(
        db=db,
        division_reader=NodeNumberPoolDivisionReader(
            db=db,
            scope_resolver=scope_resolver,
            profiles_applier=NodeProfilesApplier(
                db=db, branch=branch, profile_data_reader=ProfileDataReader(db=db, branch=branch)
            ),
        ),
    )
