from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub.core.ipam.utilization import PrefixUtilizationGetter

from . import Node

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class BuiltinIPPrefix(Node):
    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: Optional[dict] = None,
        related_node_ids: Optional[set] = None,
        filter_sensitive: bool = False,
    ) -> dict:
        response = await super().to_graphql(
            db, fields=fields, related_node_ids=related_node_ids, filter_sensitive=filter_sensitive
        )

        if fields:
            for read_only_attr in ["netmask", "hostmask", "network_address", "broadcast_address"]:
                if read_only_attr in fields:
                    response[read_only_attr] = {"value": getattr(self.prefix, read_only_attr)}  # type: ignore[attr-defined]

            if "utilization" in fields:
                getter = PrefixUtilizationGetter(db=db, ip_prefixes=[self])
                utilization = await getter.get_use_percentage(ip_prefix=self, branch_name=self._branch.name)
                response["utilization"] = {"value": int(utilization)}

        return response
