from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class WebhookTransformer(InfrahubTransform):
    query = "person_with_cars"
    timeout = 5

    async def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        return {key.upper(): value for key, value in data.items()}
