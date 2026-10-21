from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from infrahub.core.constants import InfrahubKind, MutationAction
from infrahub.core.manager import NodeManager
from infrahub.core.schema.attribute_parameters import NumberPoolRangeParameters
from infrahub.database import retry_db_transaction, within_transaction
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_range_validation import validate_number_pool_range
from infrahub.pools.number_pool_repository import NumberPoolRepository

from ...main import InfrahubMutation
from .common import (
    SCHEMA_POOL_RANGES_REFUSED,
    pool_lock,
    pool_target_attribute,
    range_bounds,
    refuse_ranges_leaving_held_numbers,
    refuse_ranges_outside_attribute,
    refuse_schema_pool,
    sync_shorthand,
)

if TYPE_CHECKING:
    from graphene import InputObjectType
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

    from ....initialization import GraphqlContext


RANGE_WITHOUT_POOL = "A number pool range must belong to a number pool"


class InfrahubNumberPoolRangeMutation(InfrahubMutation):
    """Range writes run under the pool lock allocation holds, so a range check never races another write."""

    class Meta:
        # Abstract so the inherited schema check runs on the generated subclasses only.
        abstract = True

    @classmethod
    @retry_db_transaction(name="number_pool_range_create")
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,  # noqa: ARG003
        override_data: dict[str, Any] | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        pool_input = data.get("pool") or {}
        pool = await NodeManager.find_object(
            db=graphql_context.db,
            kind=InfrahubKind.NUMBERPOOL,
            id=pool_input.get("id"),
            hfid=pool_input.get("hfid"),
            branch=branch,
        )
        refuse_schema_pool(pool=pool, message=SCHEMA_POOL_RANGES_REFUSED)
        pool_id = pool.get_id()

        async with pool_lock(pool_id=pool_id), graphql_context.db.start_transaction() as dbt:
            range_node, result = await super().mutate_create(
                info=info, data=data, branch=branch, database=dbt, override_data=override_data
            )
            await cls._validate_and_sync(
                db=dbt,
                pool=pool,
                branch=branch,
                range_node=range_node,
                user_id=graphql_context.assigned_user_id,
            )

        return range_node, result

    @classmethod
    async def _call_mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        obj: Node,
        skip_uniqueness_check: bool = False,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        pool = await cls._get_editable_pool(db=db, range_node=obj)
        pool_id = pool.get_id()

        async with pool_lock(pool_id=pool_id), within_transaction(db=db) as dbt:
            stored_bounds = (obj.get_attribute("start").value, obj.get_attribute("end").value)
            range_node, result = await super()._call_mutate_update(
                info=info, data=data, branch=branch, db=dbt, obj=obj, skip_uniqueness_check=skip_uniqueness_check
            )
            if await cls._get_pool_id(db=dbt, range_node=range_node) != pool_id:
                raise ValidationError(input_value="The field 'pool' can't be changed.")
            await cls._validate_and_sync(
                db=dbt,
                pool=pool,
                branch=branch,
                range_node=range_node,
                user_id=graphql_context.assigned_user_id,
                bounds_changed=(range_node.get_attribute("start").value, range_node.get_attribute("end").value)
                != stored_bounds,
            )

        return range_node, result

    @classmethod
    async def _delete_obj(cls, graphql_context: GraphqlContext, branch: Branch, obj: Node) -> list[Node]:
        pool = await cls._get_editable_pool(db=graphql_context.db, range_node=obj)
        pool_id = pool.get_id()

        async with pool_lock(pool_id=pool_id), graphql_context.db.start_transaction() as dbt:
            deleted = await NodeManager.delete(
                db=dbt, branch=branch, nodes=[obj], user_id=graphql_context.assigned_user_id
            )
            ranges = await NumberPoolRepository(db=dbt).get_ranges(pool_id=pool_id)
            await refuse_ranges_leaving_held_numbers(db=dbt, pool=pool, ranges=range_bounds(ranges))
            mirrored_pool = await sync_shorthand(
                db=dbt, pool_id=pool_id, ranges=ranges, user_id=graphql_context.assigned_user_id
            )
        cls._record_mirrored_pool(range_node=obj, mirrored_pool=mirrored_pool)

        return deleted

    @classmethod
    async def _get_pool_id(cls, db: InfrahubDatabase, range_node: Node) -> str:
        pool_id = await range_node.get_relationship("pool").get_peer_id(db=db)
        if pool_id is None:
            raise ValidationError(input_value=RANGE_WITHOUT_POOL)
        return pool_id

    @classmethod
    async def _get_editable_pool(cls, db: InfrahubDatabase, range_node: Node) -> Node:
        pool = await range_node.get_relationship("pool").get_peer(db=db)
        if pool is None:
            raise ValidationError(input_value=RANGE_WITHOUT_POOL)
        refuse_schema_pool(pool=pool, message=SCHEMA_POOL_RANGES_REFUSED)
        return pool

    @classmethod
    async def _validate_and_sync(
        cls,
        db: InfrahubDatabase,
        pool: Node,
        branch: Branch,
        range_node: Node,
        user_id: str,
        bounds_changed: bool = True,
    ) -> None:
        """Validate the saved range against the pool's other ranges and the attribute, then mirror the shorthand.

        Without `bounds_changed` the ranges cover the same numbers as before, so the tracked numbers are not read.
        """
        pool_id = pool.get_id()
        ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
        bounds_by_id = {bounds.id: bounds for bounds in range_bounds(ranges)}
        candidate = bounds_by_id[range_node.get_id()]
        validate_number_pool_range(candidate=candidate, others=bounds_by_id.values())
        refuse_ranges_outside_attribute(
            attribute=pool_target_attribute(db=db, pool=pool, branch=branch),
            ranges=[NumberPoolRangeParameters(start=candidate.start, end=candidate.end)],
        )
        if bounds_changed:
            await refuse_ranges_leaving_held_numbers(db=db, pool=pool, ranges=list(bounds_by_id.values()))
        mirrored_pool = await sync_shorthand(db=db, pool_id=pool_id, ranges=ranges, user_id=user_id)
        cls._record_mirrored_pool(range_node=range_node, mirrored_pool=mirrored_pool)

    @classmethod
    def _record_mirrored_pool(cls, range_node: Node, mirrored_pool: Node) -> None:
        """Give the pool its own event when the range write changed its start_range and end_range."""
        if not (mirrored_pool.has_changelog and mirrored_pool.node_changelog.has_changes):
            return
        range_node.record_mutation_write(node=mirrored_pool, action=MutationAction.UPDATED)
