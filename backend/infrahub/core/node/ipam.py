from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.ipam.size import PREFIX_SPACE_ATTRIBUTES, get_prefix_space
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
                await self._load_prefix_space_attributes(db=db)
                utilization_getter = PrefixUtilizationGetter(db=db, ip_prefixes=[self], branch=self._branch)
                utilization = await utilization_getter.get_use_percentage(ip_prefixes=[self])
                response["utilization"] = {"value": int(utilization)}

        return response

    async def get_resource_weight(self, db: InfrahubDatabase) -> int:
        await self._load_prefix_space_attributes(db=db)
        return get_prefix_space(self)

    async def _load_prefix_space_attributes(self, db: InfrahubDatabase) -> None:
        """Load the attributes that the usable address count depends on, when the query did not load them.

        An attribute that was not loaded holds its schema default, which can differ from the stored value.
        """
        missing = [name for name in PREFIX_SPACE_ATTRIBUTES if self.get_attribute(name=name).id is None]
        if not missing:
            return
        retrieved = await NodeManager.get_one(
            db=db, branch=self._branch, at=self._at, id=self.id, fields=dict.fromkeys(missing), raise_on_error=True
        )
        for name in missing:
            setattr(self, name, retrieved.get_attribute(name=name))
