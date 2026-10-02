from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import InputObjectType, Mutation
from typing_extensions import Self

from infrahub.core import protocols, registry
from infrahub.core.constants import InfrahubKind, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.database import retry_db_transaction
from infrahub.exceptions import SchemaNotFoundError, ValidationError
from infrahub.pools.number_pool_range_validation import (
    NumberRangeBounds,
    validate_number_pool_ranges,
    validate_shorthand_target,
)
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.registration import get_branches_with_schema_number_pool

from ...main import DeleteResult, InfrahubMutationMixin, InfrahubMutationOptions
from .common import pool_lock, range_bounds, sync_shorthand, within_transaction

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.database import InfrahubDatabase

    from ....initialization import GraphqlContext


BOUNDS_DESCRIBE_ONE_RANGE = "start_range and end_range are the two bounds of a single range"
BOUNDS_REQUIRED = f"{BOUNDS_DESCRIBE_ONE_RANGE}, both are required"
BOUNDS_NOT_CLEARABLE = f"{BOUNDS_DESCRIBE_ONE_RANGE}, neither can be cleared"
SHORTHAND_WITH_RANGES = "start_range/end_range cannot be combined with ranges"


class InfrahubNumberPoolMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: NodeSchema | None = None,
        _meta: InfrahubMutationOptions | None = None,
        **options: Any,
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")
        if not _meta:
            _meta = InfrahubMutationOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    @retry_db_transaction(name="resource_manager_create")
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,  # noqa: ARG003
    ) -> Any:
        graphql_context: GraphqlContext = info.context
        try:
            schema_node = registry.schema.get(name=data["node"].value)
            if not schema_node.is_generic_schema and not schema_node.is_node_schema:
                raise ValidationError(input_value="The selected model is not a Node or a Generic")
        except SchemaNotFoundError as exc:
            exc.message = "The selected model does not exist"
            raise exc

        attributes = [
            attribute for attribute in schema_node.attributes if attribute.name == data["node_attribute"].value
        ]
        if not attributes:
            raise ValidationError(input_value="The selected attribute doesn't exist in the selected model")

        attribute = attributes[0]
        if attribute.kind != "Number":
            raise ValidationError(input_value="The selected attribute is not of the kind Number")

        start_range_input = data.get("start_range")
        end_range_input = data.get("end_range")
        start_range = start_range_input.value if start_range_input else None
        end_range = end_range_input.value if end_range_input else None
        ranges_supplied = "ranges" in data.keys()
        if (start_range is not None or end_range is not None) and ranges_supplied:
            raise ValidationError(input_value=SHORTHAND_WITH_RANGES)

        shorthand: NumberRangeBounds | None = None
        if start_range is not None or end_range is not None:
            if start_range is None or end_range is None:
                raise ValidationError(input_value=BOUNDS_REQUIRED)

            if start_range > end_range:
                raise ValidationError(input_value="start_range can't be larger than end_range")

            if not isinstance(attribute.parameters, NumberAttributeParameters):
                raise ValidationError(
                    input_value="The selected attribute parameters are not of the kind NumberAttributeParameters"
                )

            if attribute.parameters.min_value is not None and start_range < attribute.parameters.min_value:
                raise ValidationError(input_value="start_range can't be less than min_value")

            if attribute.parameters.max_value is not None and end_range > attribute.parameters.max_value:
                raise ValidationError(input_value="end_range can't be larger than max_value")

            shorthand = NumberRangeBounds(start=start_range, end=end_range)

        if shorthand is None and not ranges_supplied:
            return await super().mutate_create(info=info, data=data, branch=branch)

        async with graphql_context.db.start_transaction() as dbt:
            number_pool, result = await super().mutate_create(info=info, data=data, branch=branch, database=dbt)
            pool_id = number_pool.get_id()
            async with pool_lock(pool_id=pool_id):
                repository = NumberPoolRepository(db=dbt)
                if shorthand is not None:
                    await repository.create_range(
                        pool_id=pool_id,
                        start=shorthand.start,
                        end=shorthand.end,
                        user_id=graphql_context.assigned_user_id,
                    )
                ranges = await repository.get_ranges(pool_id=pool_id)
                validate_number_pool_ranges(ranges=range_bounds(ranges))
                await sync_shorthand(db=dbt, pool_id=pool_id, ranges=ranges, user_id=graphql_context.assigned_user_id)

        return number_pool, result

    @classmethod
    @retry_db_transaction(name="resource_manager_update")
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,  # noqa: ARG003
        node: Node | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        new_node_value = data.get("node") and data.get("node").value
        new_node_attr_value = data.get("node_attribute") and data.get("node_attribute").value
        if new_node_value or new_node_attr_value:
            if node is None:
                node = await NodeManager.find_object(
                    db=graphql_context.db,
                    kind=InfrahubKind.NUMBERPOOL,
                    id=data.get("id"),
                    hfid=data.get("hfid"),
                    branch=branch,
                )
            if new_node_value and new_node_value != node.get_attribute("node").value:
                raise ValidationError(input_value="The fields 'node' or 'node_attribute' can't be changed.")
            if new_node_attr_value and new_node_attr_value != node.get_attribute("node_attribute").value:
                raise ValidationError(input_value="The fields 'node' or 'node_attribute' can't be changed.")

        return await super().mutate_update(info=info, data=data, branch=branch, node=node)

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
        shorthand_supplied = "start_range" in data.keys() or "end_range" in data.keys()
        ranges_supplied = "ranges" in data.keys()
        if not shorthand_supplied and not ranges_supplied:
            return await super()._call_mutate_update(
                info=info, data=data, branch=branch, db=db, obj=obj, skip_uniqueness_check=skip_uniqueness_check
            )

        if shorthand_supplied and obj.get_attribute("pool_type").get_value() == NumberPoolType.SCHEMA.value:
            raise ValidationError(
                input_value="start_range or end_range can't be updated on schema defined pools, update the schema in the default branch instead"
            )
        if shorthand_supplied and ranges_supplied:
            raise ValidationError(input_value=SHORTHAND_WITH_RANGES)

        graphql_context: GraphqlContext = info.context
        pool_id = obj.get_id()
        async with pool_lock(pool_id=pool_id), within_transaction(db=db) as dbt:
            # Re-read under the lock so a bound left out of the payload keeps what a concurrent range write stored.
            obj = await NodeManager.get_one_by_id_or_default_filter(
                db=dbt, id=pool_id, kind=obj.get_kind(), branch=branch
            )
            repository = NumberPoolRepository(db=dbt)
            ranges = await repository.get_ranges(pool_id=pool_id)
            if shorthand_supplied:
                validate_shorthand_target(ranges=range_bounds(ranges))

            number_pool, result = await super()._call_mutate_update(
                info=info, data=data, branch=branch, db=dbt, obj=obj, skip_uniqueness_check=skip_uniqueness_check
            )

            if shorthand_supplied:
                await cls._write_shorthand_range(
                    repository=repository,
                    number_pool=number_pool,
                    current_range=ranges[0] if ranges else None,
                    user_id=graphql_context.assigned_user_id,
                )

            ranges = await repository.get_ranges(pool_id=pool_id)
            validate_number_pool_ranges(ranges=range_bounds(ranges))
            await sync_shorthand(db=dbt, pool_id=pool_id, ranges=ranges, user_id=graphql_context.assigned_user_id)

        return number_pool, result

    @classmethod
    async def _write_shorthand_range(
        cls,
        repository: NumberPoolRepository,
        number_pool: Node,
        current_range: CoreNumberPoolRange | None,
        user_id: str,
    ) -> None:
        start = number_pool.get_attribute("start_range").value
        end = number_pool.get_attribute("end_range").value
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValidationError(input_value=BOUNDS_NOT_CLEARABLE if current_range else BOUNDS_REQUIRED)

        if start > end:
            raise ValidationError(input_value="start_range can't be larger than end_range")

        if current_range is None:
            await repository.create_range(pool_id=number_pool.get_id(), start=start, end=end, user_id=user_id)
        else:
            await repository.save_range_bounds(pool_range=current_range, start=start, end=end, user_id=user_id)

    @classmethod
    @retry_db_transaction(name="resource_manager_update")
    async def mutate_delete(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
    ) -> DeleteResult:
        graphql_context: GraphqlContext = info.context

        number_pool = await NodeManager.find_object(
            db=graphql_context.db,
            kind=protocols.CoreNumberPool,
            id=data.get("id"),
            hfid=data.get("hfid"),
            branch=branch,
        )

        violating_branches = get_branches_with_schema_number_pool(
            kind=number_pool.node.value, attribute_name=number_pool.node_attribute.value
        )

        if violating_branches:
            raise ValidationError(
                input_value=f"Unable to delete number pool {number_pool.node.value}.{number_pool.node_attribute.value}"
                f" is in use (branches: {','.join(violating_branches)})"
            )

        return await super().mutate_delete(info=info, data=data, branch=branch)
