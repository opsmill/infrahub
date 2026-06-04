from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class TagsTransform(InfrahubTransform):
    query = "tags_query"
    timeout = 10

    async def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        return data
