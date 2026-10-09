from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from infrahub.core import protocols, registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.database import retry_db_transaction, within_transaction
from infrahub.exceptions import SchemaNotFoundError, ValidationError
from infrahub.pools.number_pool_range_validation import (
    NumberRangeBounds,
    validate_number_pool_ranges,
    validate_shorthand_target,
)
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.registration import get_branches_with_schema_number_pool
from infrahub.pools.scope import SCOPE_FIELD, AllocationScope, AllocationScopeResolver, AllocationScopeValidator

from ...main import DeleteResult, InfrahubMutation
from .common import (
    SCHEMA_POOL_RANGES_REFUSED,
    SCHEMA_POOL_SHORTHAND_REFUSED,
    SCOPE_UPDATE_REFUSED,
    pool_lock,
    range_bounds,
    refuse_schema_pool,
    sync_shorthand,
)

if TYPE_CHECKING:
    from graphene import InputObjectType
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import AttributeSchema
    from infrahub.database import InfrahubDatabase

    from ....initialization import GraphqlContext


BOUNDS_DESCRIBE_ONE_RANGE = "start_range and end_range are the two bounds of a single range"
BOUNDS_REQUIRED = f"{BOUNDS_DESCRIBE_ONE_RANGE}, both are required"
BOUNDS_NOT_CLEARABLE = f"{BOUNDS_DESCRIBE_ONE_RANGE}, neither can be cleared"
SHORTHAND_WITH_RANGES = "start_range/end_range cannot be combined with ranges"


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
        cls._resolve_scope(data=data, kind=data["node"].value, attribute_name=attribute.name)
        ranges_supplied = "ranges" in data.keys()
        shorthand = cls._parse_shorthand(data=data, attribute=attribute, ranges_supplied=ranges_supplied)

        if shorthand is None and not ranges_supplied:
            return await super().mutate_create(info=info, data=data, branch=branch)

        async with graphql_context.db.start_transaction() as dbt:
            number_pool, result = await super().mutate_create(info=info, data=data, branch=branch, database=dbt)
            pool_id = number_pool.get_id()
            async with pool_lock(pool_id=pool_id):
                repository = NumberPoolRepository(db=dbt)
                if shorthand is not None:
                    await repository.create_range(
                        pool=number_pool,
                        start=shorthand.start,
                        end=shorthand.end,
                        user_id=graphql_context.assigned_user_id,
                    )
                ranges = await repository.get_ranges(pool_id=pool_id)
                validate_number_pool_ranges(ranges=range_bounds(ranges))
                await sync_shorthand(db=dbt, pool_id=pool_id, ranges=ranges, user_id=graphql_context.assigned_user_id)

        return number_pool, result

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
    def _resolve_scope(cls, data: InputObjectType, kind: str, attribute_name: str) -> None:
        """Replace the payload's allocation scope with its stored form, once the default branch's schema accepts it.

        The default branch's schema is the reference whatever branch the mutation runs on, because the pool is shared
        by every branch while the kind's fields differ between branches.

        Raises:
            ValidationError: When the scope is not a list of entries, an entry names no field of the kind, an element
                cannot divide the pool, the tracked attribute is unique, or the default branch's schema does not
                define the pool's kind.

        """
        scope_input = data.get(SCOPE_FIELD)
        if not scope_input:
            return
        entries = scope_input.get("value")
        if entries is None:
            return
        default_schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
        scope = AllocationScopeResolver(schema_branch=default_schema_branch).resolve(kind=kind, entries=entries)
        AllocationScopeValidator(schema_branch=default_schema_branch).validate(
            kind=kind, tracked_attribute=attribute_name, scope=scope
        )
        scope_input["value"] = None if scope.is_empty else scope.to_stored()

    @classmethod
    def _refuse_scope_change(cls, data: InputObjectType, pool: Node) -> None:
        """Refuse an allocation scope that differs from the stored one, and keep the stored value for one that matches.

        A matching scope is accepted so that a pool re-sent whole, as an upsert does, still saves; the sent entries
        match when they name, on the default branch's schema, the stored element ids in the stored order. The elements
        are not checked again, because the scope is never set a second time.

        Raises:
            ValidationError: When the scope is not a list of entries, an entry names no field of the pool's kind, the
                scope differs from the stored one, or the stored scope is not a list of `{id, name}` elements.

        """
        scope_input = data.get(SCOPE_FIELD)
        if not scope_input or "value" not in scope_input:
            return

        stored_value = pool.get_attribute(SCOPE_FIELD).value
        stored_scope = AllocationScope.from_stored(value=stored_value, pool=str(pool.get_attribute("name").value))
        resolver = AllocationScopeResolver(
            schema_branch=registry.schema.get_schema_branch(name=registry.default_branch)
        )
        sent_scope = resolver.resolve(kind=str(pool.get_attribute("node").value), entries=scope_input["value"])
        if [element.id for element in sent_scope.elements] != [element.id for element in stored_scope.elements]:
            raise ValidationError(input_value=SCOPE_UPDATE_REFUSED)
        scope_input["value"] = stored_value

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
        cls._refuse_scope_change(data=data, pool=obj)
        shorthand_supplied = "start_range" in data.keys() or "end_range" in data.keys()
        ranges_supplied = "ranges" in data.keys()
        if not shorthand_supplied and not ranges_supplied:
            return await super()._call_mutate_update(
                info=info, data=data, branch=branch, db=db, obj=obj, skip_uniqueness_check=skip_uniqueness_check
            )

        cls._refuse_unsupported_writes(pool=obj, shorthand_supplied=shorthand_supplied, ranges_supplied=ranges_supplied)

        graphql_context: GraphqlContext = info.context
        pool_id = obj.get_id()
        async with pool_lock(pool_id=pool_id), within_transaction(db=db) as dbt:
            # Re-read under the lock so a bound left out of the payload keeps what a concurrent range write stored.
            obj = await NodeManager.get_one(db=dbt, id=pool_id, kind=obj.get_kind(), branch=branch, raise_on_error=True)
            number_pool, result = await super()._call_mutate_update(
                info=info, data=data, branch=branch, db=dbt, obj=obj, skip_uniqueness_check=skip_uniqueness_check
            )

            repository = NumberPoolRepository(db=dbt)
            if shorthand_supplied:
                await cls._write_shorthand_range(
                    repository=repository, number_pool=number_pool, user_id=graphql_context.assigned_user_id
                )

            updated_ranges = await repository.get_ranges(pool_id=pool_id)
            validate_number_pool_ranges(ranges=range_bounds(updated_ranges))
            await sync_shorthand(
                db=dbt, pool_id=pool_id, ranges=updated_ranges, user_id=graphql_context.assigned_user_id
            )

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
    async def _write_shorthand_range(cls, repository: NumberPoolRepository, number_pool: Node, user_id: str) -> None:
        """Write the pool's start_range / end_range to its single range, creating the range when the pool holds none.

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

        if stored_range is None:
            await repository.create_range(pool=number_pool, start=start, end=end, user_id=user_id)
        else:
            await repository.save_range_bounds(pool_range=stored_range, start=start, end=end, user_id=user_id)

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
