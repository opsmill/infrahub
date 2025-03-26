from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

from graphene import Field, Int, ObjectType, String
from netaddr import IPSet

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.query.ipam import get_ip_addresses, get_subnets
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.pools.address import get_available
from infrahub.pools.prefix import get_next_available_prefix

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class IPAddressGetNextAvailable(ObjectType):
    address = String(required=True)

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        prefix_id: str,
        prefix_length: int | None = None,
    ) -> dict[str, str]:
        graphql_context: GraphqlContext = info.context

        prefix = await NodeManager.get_one(id=prefix_id, db=graphql_context.db, branch=graphql_context.branch)

        if not prefix:
            raise NodeNotFoundError(
                branch_name=graphql_context.branch.name, node_type=InfrahubKind.IPPREFIX, identifier=prefix_id
            )

        ip_prefix = ipaddress.ip_network(prefix.prefix.value)  # type: ignore[attr-defined]
        prefix_length = prefix_length or ip_prefix.prefixlen

        if not ip_prefix.prefixlen <= prefix_length <= ip_prefix.max_prefixlen:
            raise ValidationError(input_value="Invalid prefix length for current selected prefix")

        namespace = await prefix.ip_namespace.get_peer(db=graphql_context.db)  # type: ignore[attr-defined]
        addresses = await get_ip_addresses(
            db=graphql_context.db,
            ip_prefix=ip_prefix,
            namespace=namespace,
            branch=graphql_context.branch,
        )

        available = get_available(
            network=ip_prefix,
            addresses=[ip.address for ip in addresses],
            is_pool=prefix.is_pool.value,  # type: ignore[attr-defined]
        )

        if not available:
            raise IndexError("No addresses available in prefix")

        next_address = available.iter_cidrs()[0]

        return {"address": f"{next_address.ip}/{prefix_length}"}


class IPPrefixGetNextAvailable(ObjectType):
    prefix = String(required=True)

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        prefix_id: str,
        prefix_length: int,
    ) -> dict[str, str]:
        graphql_context: GraphqlContext = info.context

        prefix = await NodeManager.get_one(id=prefix_id, db=graphql_context.db, branch=graphql_context.branch)

        if not prefix:
            raise NodeNotFoundError(
                branch_name=graphql_context.branch.name, node_type=InfrahubKind.IPPREFIX, identifier=prefix_id
            )

        namespace = await prefix.ip_namespace.get_peer(db=graphql_context.db)  # type: ignore[attr-defined]
        subnets = await get_subnets(
            db=graphql_context.db,
            ip_prefix=ipaddress.ip_network(prefix.prefix.value),  # type: ignore[attr-defined]
            namespace=namespace,
            branch=graphql_context.branch,
        )

        pool = IPSet([prefix.prefix.value])
        for subnet in subnets:
            pool.remove(addr=str(subnet.prefix))

        prefix_ver = ipaddress.ip_network(prefix.prefix.value).version
        next_available = get_next_available_prefix(pool=pool, prefix_length=prefix_length, prefix_ver=prefix_ver)

        return {"prefix": str(next_available)}


InfrahubIPAddressGetNextAvailable = Field(
    IPAddressGetNextAvailable,
    prefix_id=String(required=True),
    prefix_length=Int(required=False),
    resolver=IPAddressGetNextAvailable.resolve,
    required=True,
)


InfrahubIPPrefixGetNextAvailable = Field(
    IPPrefixGetNextAvailable,
    prefix_id=String(required=True),
    prefix_length=Int(required=False),
    resolver=IPPrefixGetNextAvailable.resolve,
    required=True,
)
