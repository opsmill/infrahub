from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, InputField, InputObjectType, Int, List, Mutation, String
from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, MutationAction
from infrahub.core.ipam.constants import PrefixMemberType
from infrahub.exceptions import QueryValidationError
from infrahub.graphql.scalars import FixedGenericScalar

from ...queries.resource_manager import PoolAllocatedNode
from ..main import emit_node_mutation_events

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
    from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool

    from ...initialization import GraphqlContext


class IPPrefixPoolGetResourceInput(InputObjectType):
    id = InputField(String(required=False), description="ID of the pool to allocate from")
    hfid = InputField(List(of_type=String, required=False), description="HFID of the pool to allocate from")
    identifier = InputField(String(required=False), description="Identifier for the allocated resource")
    prefix_length = InputField(Int(required=False), description="Size of the prefix to allocate")
    member_type = InputField(String(required=False), description="Type of members for the newly created prefix")
    prefix_type = InputField(String(required=False), description="Kind of prefix to allocate")
    data = InputField(
        FixedGenericScalar, required=False, description="Additional data to pass to the newly created prefix"
    )


class IPAddressPoolGetResourceInput(InputObjectType):
    id = InputField(String(required=False), description="ID of the pool to allocate from")
    hfid = InputField(List(of_type=String, required=False), description="HFID of the pool to allocate from")
    identifier = InputField(String(required=False), description="Identifier for the allocated resource")
    prefix_length = InputField(
        Int(required=False), description="Size of the prefix mask to allocate on the new IP address"
    )
    address_type = InputField(String(required=False), description="Kind of IP address to allocate")
    data = InputField(
        FixedGenericScalar, required=False, description="Additional data to pass to the newly created IP address"
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
            # No relationship context here, so the broadest legal peer is the builtin IP prefix generic.
            peer_kind=InfrahubKind.IPPREFIX,
            data=data.get("data", None),
            user_id=graphql_context.assigned_user_id,
        )

        await emit_node_mutation_events(node=resource, graphql_context=graphql_context, action=MutationAction.CREATED)

        result = {
            "ok": True,
            "node": {
                "id": resource.id,
                "kind": resource.get_kind(),
                "identifier": data.get("identifier", None),
                "display_label": await resource.get_display_label(db=graphql_context.db),
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

        obj: CoreIPAddressPool = await registry.manager.find_object(  # type: ignore[assignment]
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
            # No relationship context here, so the broadest legal peer is the builtin IP address generic.
            peer_kind=InfrahubKind.IPADDRESS,
            data=data.get("data"),
            user_id=graphql_context.assigned_user_id,
        )

        await emit_node_mutation_events(node=resource, graphql_context=graphql_context, action=MutationAction.CREATED)

        result = {
            "ok": True,
            "node": {
                "id": resource.id,
                "kind": resource.get_kind(),
                "identifier": data.get("identifier"),
                "display_label": await resource.get_display_label(db=graphql_context.db),
                "branch": graphql_context.branch.name,
            },
        }

        return cls(**result)
