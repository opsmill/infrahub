from typing import TYPE_CHECKING, Any, Dict

from graphene import Boolean, Field, InputField, InputObjectType, Int, Mutation, String
from graphene.types.generic import GenericScalar
from graphql import GraphQLResolveInfo
from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.constants import PrefixMemberType
from infrahub.exceptions import QueryValidationError

from ..queries.resource_manager import PoolAllocatedNode

if TYPE_CHECKING:
    from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
    from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool

    from .. import GraphqlContext


class IPPrefixPoolGetResourceInput(InputObjectType):
    id = InputField(String(required=False), description="ID of the pool to allocate from")
    hfid = InputField(String(required=False), description="HFID of the pool to allocate from")
    identifier = InputField(String(required=False), description="Identifier for the allocated resource")
    prefix_length = InputField(Int(required=False), description="Size of the prefix to allocate")
    member_type = InputField(String(required=False), description="member_type of the newly created prefix")
    prefix_type = InputField(String(required=False), description="Kind of prefix to allocate")
    data = InputField(GenericScalar(required=False), description="Additional data to pass to the newly created prefix")


class IPAddressPoolGetResourceInput(InputObjectType):
    id = InputField(String(required=False), description="ID of the pool to allocate from")
    hfid = InputField(String(required=False), description="HFID of the pool to allocate from")
    identifier = InputField(String(required=False), description="Identifier for the allocated resource")
    prefix_length = InputField(
        Int(required=False), description="Size of the prefix mask to allocate on the new IP address"
    )
    address_type = InputField(String(required=False), description="Kind of ip address to allocate")
    data = InputField(
        GenericScalar(required=False), description="Additional data to pass to the newly created ip address"
    )


class IPPrefixPoolGetResource(Mutation):
    class Arguments:
        data = IPPrefixPoolGetResourceInput(required=True)

    ok = Boolean()
    node = Field(PoolAllocatedNode)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: InputObjectType,
    ) -> Self:
        context: GraphqlContext = info.context

        member_type = data.get("member_type", None)
        allowed_member_types = [t.value for t in PrefixMemberType]
        if member_type and member_type not in allowed_member_types:
            raise QueryValidationError(f"Invalid member_type value, allowed values are {allowed_member_types}")

        obj: CoreIPPrefixPool = await registry.manager.find_object(  # type: ignore[assignment]
            db=context.db,
            kind=InfrahubKind.IPPREFIXPOOL,
            id=data.get("id"),
            hfid=data.get("hfid"),
            branch=context.branch,
            at=context.at,
        )
        resource = await obj.get_resource(
            db=context.db,
            branch=context.branch,
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
                "display_label": await resource.render_display_label(db=context.db),
                "branch": context.branch.name,
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
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: Dict[str, Any],
    ) -> Self:
        context: GraphqlContext = info.context

        obj: CoreIPAddressPool = await registry.manager.find_object(  # type: ignore[assignment]
            db=context.db,
            kind=InfrahubKind.IPADDRESSPOOL,
            id=data.get("id"),
            hfid=data.get("hfid"),
            branch=context.branch,
            at=context.at,
        )
        resource = await obj.get_resource(
            db=context.db,
            branch=context.branch,
            identifier=data.get("identifier", None),
            prefixlen=data.get("prefix_length", None),
            address_type=data.get("address_type", None),
            data=data.get("data", None),
        )

        result = {
            "ok": True,
            "node": {
                "id": resource.id,
                "kind": resource.get_kind(),
                "identifier": data.get("identifier", None),
                "display_label": await resource.render_display_label(db=context.db),
                "branch": context.branch.name,
            },
        }

        return cls(**result)
