from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class TShirtBadge(InfrahubTransform):
    """Reads the peer's display label, which no read set can map to backing fields.

    The read set is therefore imprecise, which is the case the coalesced pass has to handle by
    asking who reads the changed nodes rather than by refreshing the whole kind.
    """

    query = "tshirt_badge"

    async def transform(self, data: dict[str, Any]) -> str:
        node = data["TestingTShirt"]["edges"][0]["node"]
        return f"{node['name']['value']} in {node['color']['node']['display_label']}"
