from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, InputField, InputObjectType, Int, List, Mutation, String
from graphene.types.generic import GenericScalar
from typing_extensions import Self

from infrahub.core import protocols, registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.constants import PrefixMemberType
from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.database import retry_db_transaction
from infrahub.exceptions import QueryValidationError, SchemaNotFoundError, ValidationError
from infrahub.pools.registration import get_branches_with_schema_number_pool

from ..queries.resource_manager import PoolAllocatedNode
from .main import DeleteResult, InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
    from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
    from infrahub.database import InfrahubDatabase

    from ..initialization import GraphqlContext


class IPPrefixPoolGetResourceInput(InputObjectType):
    id = InputField(String(required=False), description="ID of the pool to allocate from")
    hfid = InputField(List(of_type=String, required=False), description="HFID of the pool to allocate from")
    identifier = InputField(String(required=False), description="Identifier for the allocated resource")
    prefix_length = InputField(Int(required=False), description="Size of the prefix to allocate")
    member_type = InputField(String(required=False), description="Type of members for the newly created prefix")
    prefix_type = InputField(String(required=False), description="Kind of prefix to allocate")
    data = InputField(GenericScalar(required=False), description="Additional data to pass to the newly created prefix")


class IPAddressPoolGetResourceInput(InputObjectType):
    id = InputField(String(required=False), description="ID of the pool to allocate from")
    hfid = InputField(List(of_type=String, required=False), description="HFID of the pool to allocate from")
    identifier = InputField(String(required=False), description="Identifier for the allocated resource")
    prefix_length = InputField(
        Int(required=False), description="Size of the prefix mask to allocate on the new IP address"
    )
    address_type = InputField(String(required=False), description="Kind of IP address to allocate")
    data = InputField(
        GenericScalar(required=False), description="Additional data to pass to the newly created IP address"
    )


class IPPrefixPoolGetResource(Mutation):
    class Arguments:
        data = IPPrefixPoolGetResourceInput(required=True)

    ok = Boolean()
    node = Field(PoolAllocatedNode)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: InputObjectType,
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        member_type = data.get("member_type", None)
        allowed_member_types = [t.value for t in PrefixMemberType]
        if member_type and member_type not in allowed_member_types:
            raise QueryValidationError(f"Invalid member_type value, allowed values are {allowed_member_types}")

        obj: CoreIPPrefixPool = await registry.manager.find_object(  # type: ignore[assignment]
            db=graphql_context.db,
            kind=InfrahubKind.IPPREFIXPOOL,
            id=data.get("id"),
            hfid=data.get("hfid"),
            branch=graphql_context.branch,
        )
        resource = await obj.get_resource(
            db=graphql_context.db,
            branch=graphql_context.branch,
            identifier=data.get("identifier", None),
            prefixlen=data.get("prefix_length", None),
            member_type=member_type,
            prefix_type=data.get("prefix_type", None),
            data=data.get("data", None),
        )

        result = {
            "ok": True,
            "node": {
                "id": resource.id,
                "kind": resource.get_kind(),
                "identifier": data.get("identifier", None),
                "display_label": await resource.render_display_label(db=graphql_context.db),
                "branch": graphql_context.branch.name,
            },
        }

        return cls(**result)


class IPAddressPoolGetResource(Mutation):
    class Arguments:
        data = IPAddressPoolGetResourceInput(required=True)

    ok = Boolean()
    node = Field(PoolAllocatedNode)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: dict[str, Any],
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        obj: CoreIPAddressPool = await registry.manager.find_object(
            db=graphql_context.db,
            kind=InfrahubKind.IPADDRESSPOOL,
            id=data.get("id"),
            hfid=data.get("hfid"),
            branch=graphql_context.branch,
        )
        resource = await obj.get_resource(
            db=graphql_context.db,
            branch=graphql_context.branch,
            identifier=data.get("identifier"),
            prefixlen=data.get("prefix_length"),
            address_type=data.get("address_type"),
            data=data.get("data"),
        )

        result = {
            "ok": True,
            "node": {
                "id": resource.id,
                "kind": resource.get_kind(),
                "identifier": data.get("identifier"),
                "display_label": await resource.render_display_label(db=graphql_context.db),
                "branch": graphql_context.branch.name,
            },
        }

        return cls(**result)


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

        start_range = data["start_range"].value
        end_range = data["end_range"].value
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
        if (data.get("node") and data.get("node").value) or (
            data.get("node_attribute") and data.get("node_attribute").value
        ):
            raise ValidationError(input_value="The fields 'node' or 'node_attribute' can't be changed.")
        graphql_context: GraphqlContext = info.context

        async with graphql_context.db.start_transaction() as dbt:
            number_pool, result = await super().mutate_update(
                info=info, data=data, branch=branch, database=dbt, node=node
            )
            if number_pool.start_range.value > number_pool.end_range.value:  # type: ignore[attr-defined]
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
