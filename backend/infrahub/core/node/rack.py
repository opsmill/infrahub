from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.rack_elevation.constants import RackTotalAttribute
from infrahub.rack_elevation.placement import compute_totals
from infrahub.rack_elevation.provider import build_rack_elevation_provider

from . import Node

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class RackElevationRackNode(Node):
    """A node of a kind with the `rack` role: its totals are calculated when a query asks for them."""

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

        requested = [name for name in RackTotalAttribute.available_types() if fields and name in fields]
        if requested:
            provider = build_rack_elevation_provider(db=db, branch=self._branch, at=self._at)
            rack, items = await provider.load_rack(rack_id=self.get_id())
            totals = compute_totals(rack=rack, items=items)
            values = {
                RackTotalAttribute.USED_UNITS.value: totals.used_units,
                RackTotalAttribute.UTILIZATION.value: totals.utilization,
                RackTotalAttribute.TOTAL_WEIGHT.value: totals.total_weight,
            }
            for name in requested:
                response[name] = {"value": values[name]}

        return response
