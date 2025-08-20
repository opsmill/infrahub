from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class Multiplier(InfrahubTransform):
    query = "multiplier"
    url = "multiply"

    async def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        multiplier = int(data.pop("multiplier", 1))
        return {key: value * multiplier for key, value in data.items()}


INFRAHUB_TRANSFORMS = [Multiplier]
