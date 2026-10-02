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
from infrahub.pools.registration import get_branches_with_schema_number_pool

from ...main import DeleteResult, InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

    from ....initialization import GraphqlContext


BOUNDS_DESCRIBE_ONE_RANGE = "start_range and end_range are the two bounds of a single range"
BOUNDS_REQUIRED = f"{BOUNDS_DESCRIBE_ONE_RANGE}, both are required"
BOUNDS_NOT_CLEARABLE = f"{BOUNDS_DESCRIBE_ONE_RANGE}, neither can be cleared"


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

        return await super().mutate_create(info=info, data=data, branch=branch)

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

        async with graphql_context.db.start_transaction() as dbt:
            number_pool, result = await super().mutate_update(
                info=info, data=data, branch=branch, database=dbt, node=node
            )

            if number_pool.get_attribute("pool_type").get_value() == NumberPoolType.SCHEMA.value and (
                "start_range" in data.keys() or "end_range" in data.keys()
            ):
                raise ValidationError(
                    input_value="start_range or end_range can't be updated on schema defined pools, update the schema in the default branch instead"
                )

            if "start_range" in data.keys() or "end_range" in data.keys():
                start_value = number_pool.get_attribute("start_range").value
                end_value = number_pool.get_attribute("end_range").value
                if start_value is None or end_value is None:
                    raise ValidationError(input_value=BOUNDS_NOT_CLEARABLE)

                if start_value > end_value:
                    raise ValidationError(input_value="start_range can't be larger than end_range")

        return number_pool, result

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
