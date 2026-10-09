from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from infrahub.core import protocols, registry
from infrahub.core.constants import InfrahubKind, PermissionAction
from infrahub.core.manager import NodeManager
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters, NumberPoolRangeParameters
from infrahub.database import retry_db_transaction, within_transaction
from infrahub.exceptions import SchemaNotFoundError, ValidationError
from infrahub.permissions.types import define_object_permission_from_branch
from infrahub.pools.number_pool_range_reconciler import NumberPoolRangeReconciler, RangeReconciliation
from infrahub.pools.number_pool_range_validation import (
    NumberRangeBounds,
    validate_number_pool_ranges,
    validate_shorthand_target,
)
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.registration import get_branches_with_schema_number_pool

from ...main import DeleteResult, InfrahubMutation, build_graphql_response
from .common import (
    SCHEMA_POOL_RANGES_REFUSED,
    SCHEMA_POOL_SHORTHAND_REFUSED,
    pool_lock,
    range_bounds,
    refuse_schema_pool,
    sync_shorthand,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from graphene import InputObjectType
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.core.schema import AttributeSchema
    from infrahub.database import InfrahubDatabase

    from ....initialization import GraphqlContext


BOUNDS_DESCRIBE_ONE_RANGE = "start_range and end_range are the two bounds of a single range"
BOUNDS_REQUIRED = f"{BOUNDS_DESCRIBE_ONE_RANGE}, both are required"
BOUNDS_NOT_CLEARABLE = f"{BOUNDS_DESCRIBE_ONE_RANGE}, neither can be cleared"
SHORTHAND_WITH_RANGES = "start_range/end_range cannot be combined with ranges"
RANGES_NOT_NULLABLE = "ranges cannot be null, send an empty list to remove every range"


class InfrahubNumberPoolMutation(InfrahubMutation):
    class Meta:
        # Abstract so the inherited schema check runs on the generated subclasses only.
        abstract = True

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
        attribute = cls._resolve_target_attribute(data=data)
        shorthand = cls._parse_shorthand(data=data, attribute=attribute, ranges_supplied="ranges" in data.keys())
        declared_ranges = cls._parse_ranges(data=data)
        if shorthand is not None:
            declared_ranges = [NumberPoolRangeParameters(start=shorthand.start, end=shorthand.end)]

        if declared_ranges is None:
            return await super().mutate_create(info=info, data=data, branch=branch)

        async with graphql_context.db.start_transaction() as dbt:
            number_pool, _ = await super().mutate_create(
                info=info,
                data=cls._without_ranges(data=data),
                branch=branch,
                database=dbt,
            )
            pool_id = number_pool.get_id()
            async with pool_lock(pool_id=pool_id):
                reconciler = NumberPoolRangeReconciler(range_store=NumberPoolRepository(db=dbt))
                if shorthand is None:
                    reconciliation = await reconciler.reconcile(
                        pool=number_pool, declared=declared_ranges, user_id=graphql_context.assigned_user_id
                    )
                    cls._raise_for_range_permissions(graphql_context=graphql_context, reconciliation=reconciliation)
                else:
                    reconciliation = await reconciler.rewrite_single_range(
                        pool=number_pool, declared=declared_ranges[0], user_id=graphql_context.assigned_user_id
                    )
                stored_pool = await sync_shorthand(
                    db=dbt, pool_id=pool_id, ranges=reconciliation.ranges, user_id=graphql_context.assigned_user_id
                )
                result = cls(**await build_graphql_response(info=info, db=dbt, obj=stored_pool))

        return number_pool, result

    @classmethod
    def _parse_ranges(cls, data: InputObjectType) -> list[NumberPoolRangeParameters] | None:
        """Return the ranges the payload declares, or None when it leaves `ranges` out.

        Raises:
            ValidationError: When `ranges` is null, or a declared range is backwards or overlaps another one.

        """
        if "ranges" not in data.keys():
            return None
        if data.get("ranges") is None:
            raise ValidationError(input_value=RANGES_NOT_NULLABLE)

        declared = [
            NumberPoolRangeParameters(
                start=declared_range["start"],
                end=declared_range["end"],
                weight=declared_range.get("allocation_weight"),
            )
            for declared_range in data["ranges"]
        ]
        validate_number_pool_ranges(
            ranges=[
                NumberRangeBounds(start=declared_range.start, end=declared_range.end, id=f"ranges[{index}]")
                for index, declared_range in enumerate(declared)
            ]
        )
        return declared

    @classmethod
    def _raise_for_range_permissions(
        cls, graphql_context: GraphqlContext, reconciliation: RangeReconciliation[CoreNumberPoolRange]
    ) -> None:
        """Refuse range writes the account may not make through the range mutations themselves.

        Raises:
            PermissionDeniedError: When the account lacks the create, update or delete permission on ranges that
                one of the writes needs.

        """
        if not graphql_context.account_session:
            return
        branch_name = graphql_context.branch.name
        range_schema = graphql_context.db.schema.get_node_schema(
            name=InfrahubKind.NUMBERPOOLRANGE, branch=branch_name, duplicate=False
        )
        for action, pool_ranges in (
            (PermissionAction.CREATE, reconciliation.created),
            (PermissionAction.UPDATE, reconciliation.updated),
            (PermissionAction.DELETE, reconciliation.deleted),
        ):
            if pool_ranges:
                graphql_context.active_permissions.raise_for_permission(
                    permission=define_object_permission_from_branch(
                        schema=range_schema, action=action, branch_name=branch_name
                    )
                )

    @classmethod
    def _without_ranges(cls, data: InputObjectType) -> InputObjectType:
        """Return the payload without `ranges`, which the generic node write would read as references to peers."""
        return type(data)({key: value for key, value in data.items() if key != "ranges"})

    @classmethod
    def _resolve_target_attribute(cls, data: InputObjectType) -> AttributeSchema:
        """Return the Number attribute the pool allocates for.

        Raises:
            SchemaNotFoundError: When the selected model does not exist.
            ValidationError: When the model is not a node or a generic, or the attribute is missing or not a Number.

        """
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
        return attribute

    @classmethod
    def _parse_shorthand(
        cls, data: InputObjectType, attribute: AttributeSchema, ranges_supplied: bool
    ) -> NumberRangeBounds | None:
        """Return the single range the shorthand describes, or None when neither bound is supplied.

        Raises:
            ValidationError: When the shorthand comes with `ranges`, misses a bound, is backwards, or falls outside
                the attribute's `min_value` / `max_value`.

        """
        start_range_input = data.get("start_range")
        end_range_input = data.get("end_range")
        start_range = start_range_input.value if start_range_input else None
        end_range = end_range_input.value if end_range_input else None
        if start_range is None and end_range is None:
            return None
        if ranges_supplied:
            raise ValidationError(input_value=SHORTHAND_WITH_RANGES)
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

        return NumberRangeBounds(start=start_range, end=end_range)

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

        cls._refuse_unsupported_writes(pool=obj, shorthand_supplied=shorthand_supplied, ranges_supplied=ranges_supplied)
        declared_ranges = cls._parse_ranges(data=data)

        graphql_context: GraphqlContext = info.context
        pool_id = obj.get_id()
        async with pool_lock(pool_id=pool_id), within_transaction(db=db) as dbt:
            # Re-read under the lock so a bound left out of the payload keeps what a concurrent range write stored.
            obj = await NodeManager.get_one(db=dbt, id=pool_id, kind=obj.get_kind(), branch=branch, raise_on_error=True)
            number_pool, _ = await super()._call_mutate_update(
                info=info,
                data=cls._without_ranges(data=data),
                branch=branch,
                db=dbt,
                obj=obj,
                skip_uniqueness_check=skip_uniqueness_check,
            )

            repository = NumberPoolRepository(db=dbt)
            reconciler = NumberPoolRangeReconciler(range_store=repository)
            if declared_ranges is None:
                shorthand_range = await cls._shorthand_range(repository=repository, number_pool=number_pool)
                reconciliation = await reconciler.rewrite_single_range(
                    pool=number_pool, declared=shorthand_range, user_id=graphql_context.assigned_user_id
                )
            else:
                declared_ranges = await cls._keep_stored_weights(
                    repository=repository, pool_id=pool_id, declared=declared_ranges, data=data
                )
                reconciliation = await reconciler.reconcile(
                    pool=number_pool, declared=declared_ranges, user_id=graphql_context.assigned_user_id
                )
                cls._raise_for_range_permissions(graphql_context=graphql_context, reconciliation=reconciliation)
            stored_pool = await sync_shorthand(
                db=dbt, pool_id=pool_id, ranges=reconciliation.ranges, user_id=graphql_context.assigned_user_id
            )
            result = await cls.mutate_update_to_graphql(db=dbt, info=info, obj=stored_pool)

        return number_pool, result

    @classmethod
    def _refuse_unsupported_writes(cls, pool: Node, shorthand_supplied: bool, ranges_supplied: bool) -> None:
        """Refuse a shorthand or `ranges` write on a schema-created pool, and the shorthand alongside `ranges`.

        Raises:
            ValidationError: On either refusal, the schema-created pool one first.

        """
        refuse_schema_pool(
            pool=pool, message=SCHEMA_POOL_SHORTHAND_REFUSED if shorthand_supplied else SCHEMA_POOL_RANGES_REFUSED
        )
        if shorthand_supplied and ranges_supplied:
            raise ValidationError(input_value=SHORTHAND_WITH_RANGES)

    @classmethod
    async def _keep_stored_weights(
        cls,
        repository: NumberPoolRepository,
        pool_id: str,
        declared: Sequence[NumberPoolRangeParameters],
        data: InputObjectType,
    ) -> list[NumberPoolRangeParameters]:
        """Give a range redeclared with its stored bounds and no `allocation_weight` the weight it holds."""
        bounds_without_weight = {
            (declared_range["start"], declared_range["end"])
            for declared_range in data["ranges"]
            if "allocation_weight" not in declared_range.keys()
        }
        stored_weights = {
            (int(pool_range.start.value), int(pool_range.end.value)): pool_range.allocation_weight.value
            for pool_range in await repository.get_ranges(pool_id=pool_id)
        }
        return [
            NumberPoolRangeParameters(start=declared_range.start, end=declared_range.end, weight=stored_weights[bounds])
            if (bounds := (declared_range.start, declared_range.end)) in bounds_without_weight
            and bounds in stored_weights
            else declared_range
            for declared_range in declared
        ]

    @classmethod
    async def _shorthand_range(cls, repository: NumberPoolRepository, number_pool: Node) -> NumberPoolRangeParameters:
        """Return the single range the pool's start_range / end_range describe, keeping the weight it holds.

        Raises:
            ValidationError: When the pool holds more than one range, a bound is missing or cleared, or the
                bounds are backwards.

        """
        stored_ranges = await repository.get_ranges(pool_id=number_pool.get_id())
        validate_shorthand_target(ranges=range_bounds(stored_ranges))
        stored_range = stored_ranges[0] if stored_ranges else None

        start = number_pool.get_attribute("start_range").value
        end = number_pool.get_attribute("end_range").value
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValidationError(input_value=BOUNDS_NOT_CLEARABLE if stored_range else BOUNDS_REQUIRED)

        if start > end:
            raise ValidationError(input_value="start_range can't be larger than end_range")

        weight = stored_range.allocation_weight.value if stored_range else None
        return NumberPoolRangeParameters(start=start, end=end, weight=weight)

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

        async with pool_lock(pool_id=number_pool.get_id()):
            return await super().mutate_delete(info=info, data=data, branch=branch)

    @classmethod
    async def _delete_obj(cls, graphql_context: GraphqlContext, branch: Branch, obj: Node) -> list[Node]:  # noqa: ARG003
        return await NumberPoolRepository(db=graphql_context.db).delete_pool(
            pool_id=obj.get_id(), user_id=graphql_context.assigned_user_id
        )
