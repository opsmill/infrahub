from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.ipam.size import get_prefix_space
from infrahub.core.ipam.utilization import PrefixUtilizationGetter
from infrahub.core.manager import NodeManager

from . import Node

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class BuiltinIPPrefix(Node):
    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: dict | None = None,
        related_node_ids: set | None = None,
        filter_sensitive: bool = False,
        permissions: dict | None = None,  # noqa: ARG002
        include_properties: bool = True,
    ) -> dict:
        response = await super().to_graphql(
            db,
            fields=fields,
            related_node_ids=related_node_ids,
            filter_sensitive=filter_sensitive,
            include_properties=include_properties,
        )

        if fields:
            for read_only_attr in ["netmask", "hostmask", "network_address", "broadcast_address"]:
                if read_only_attr in fields:
                    response[read_only_attr] = {"value": getattr(self.prefix, read_only_attr)}  # type: ignore[attr-defined,has-type]

            if "utilization" in fields:
                if self.member_type.id is None or self.prefix.id is None:  # type: ignore[has-type]
                    retrieved = await NodeManager.get_one(
                        db=db, branch=self._branch, id=self.id, fields={"member_type": None, "prefix": None}
                    )
                    self.member_type = retrieved.member_type  # type: ignore[union-attr]
                    self.prefix = retrieved.prefix  # type: ignore[union-attr]
                utilization_getter = PrefixUtilizationGetter(db=db, ip_prefixes=[self])
                utilization = await utilization_getter.get_use_percentage(
                    ip_prefixes=[self], branch_names=[self._branch.name]
                )
                response["utilization"] = {"value": int(utilization)}

        return response

    async def get_resource_weight(self, db: InfrahubDatabase) -> int:
        member_type = self.member_type.value  # type: ignore[has-type]
        prefixlen = self.prefix.prefixlen  # type: ignore[has-type]
        if member_type is None or prefixlen is None:
            retrieved = await NodeManager.get_one(
                db=db, branch=self._branch, id=self.id, fields={"member_type": None, "prefix": None}
            )
            self.member_type = retrieved.member_type  # type: ignore[union-attr]
            self.prefix = retrieved.prefix  # type: ignore[union-attr]
        return get_prefix_space(self)
