from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

from graphene import Field, Int, ObjectType, String

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.query.ipam import get_subnets
from infrahub.exceptions import NodeNotFoundError
from infrahub.pools.prefix import PrefixPool

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql import GraphqlContext


class IPPrefixGetNextAvailable(ObjectType):
    prefix = String(required=True)

    @staticmethod
    async def resolve(
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        prefix_id: str,
        size: int,
    ) -> dict[str, str]:
        context: GraphqlContext = info.context

        prefix = await NodeManager.get_one(id=prefix_id, db=context.db, branch=context.branch)

        if not prefix:
            raise NodeNotFoundError(
                branch_name=context.branch.name, node_type=InfrahubKind.IPPREFIX, identifier=prefix_id
            )

        namespace = await prefix.ip_namespace.get_peer(db=context.db)  # type: ignore[attr-defined]
        subnets = await get_subnets(
            db=context.db,
            ip_prefix=ipaddress.ip_network(prefix.prefix.value),  # type: ignore[attr-defined]
            namespace=namespace,
            branch=context.branch,
        )

        pool = PrefixPool(prefix.prefix.value)  # type: ignore[attr-defined]
        for subnet in subnets:
            pool.reserve(subnet=str(subnet.prefix))

        next_available = pool.get(size=size)
        return {"prefix": str(next_available)}


InfrahubIPPrefixGetNextAvailable = Field(
    IPPrefixGetNextAvailable,
    prefix_id=String(required=True),
    size=Int(required=False),
    resolver=IPPrefixGetNextAvailable.resolve,
)
