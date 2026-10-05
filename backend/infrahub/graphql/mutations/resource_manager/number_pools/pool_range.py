from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.database import retry_db_transaction
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_range_validation import validate_number_pool_range
from infrahub.pools.number_pool_repository import NumberPoolRepository

from ...main import InfrahubMutation
from .common import pool_lock, range_bounds, sync_shorthand, within_transaction

if TYPE_CHECKING:
    from graphene import InputObjectType
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

    from ....initialization import GraphqlContext


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
        pool_id = pool.get_id()

        async with pool_lock(pool_id=pool_id), graphql_context.db.start_transaction() as dbt:
            range_node, result = await super().mutate_create(
                info=info, data=data, branch=branch, database=dbt, override_data=override_data
            )
            await cls._validate_and_sync(
                db=dbt, pool_id=pool_id, range_id=range_node.get_id(), user_id=graphql_context.assigned_user_id
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
        pool_id = await cls._get_pool_id(db=db, range_node=obj)

        async with pool_lock(pool_id=pool_id), within_transaction(db=db) as dbt:
            range_node, result = await super()._call_mutate_update(
                info=info, data=data, branch=branch, db=dbt, obj=obj, skip_uniqueness_check=skip_uniqueness_check
            )
            if await cls._get_pool_id(db=dbt, range_node=range_node) != pool_id:
                raise ValidationError(input_value="The field 'pool' can't be changed.")
            await cls._validate_and_sync(
                db=dbt, pool_id=pool_id, range_id=range_node.get_id(), user_id=graphql_context.assigned_user_id
            )

        return range_node, result

    @classmethod
    async def _delete_obj(cls, graphql_context: GraphqlContext, branch: Branch, obj: Node) -> list[Node]:
        pool_id = await cls._get_pool_id(db=graphql_context.db, range_node=obj)

        async with pool_lock(pool_id=pool_id), graphql_context.db.start_transaction() as dbt:
            deleted = await NodeManager.delete(
                db=dbt, branch=branch, nodes=[obj], user_id=graphql_context.assigned_user_id
            )
            await sync_shorthand(
                db=dbt,
                pool_id=pool_id,
                ranges=await NumberPoolRepository(db=dbt).get_ranges(pool_id=pool_id),
                user_id=graphql_context.assigned_user_id,
            )

        return deleted

    @classmethod
    async def _get_pool_id(cls, db: InfrahubDatabase, range_node: Node) -> str:
        pool_id = await range_node.get_relationship("pool").get_peer_id(db=db)
        if pool_id is None:
            raise ValidationError(input_value="A number pool range must belong to a number pool")
        return pool_id

    @classmethod
    async def _validate_and_sync(cls, db: InfrahubDatabase, pool_id: str, range_id: str, user_id: str) -> None:
        ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
        bounds_by_id = {bounds.id: bounds for bounds in range_bounds(ranges)}
        validate_number_pool_range(candidate=bounds_by_id[range_id], others=bounds_by_id.values())
        await sync_shorthand(db=db, pool_id=pool_id, ranges=ranges, user_id=user_id)
