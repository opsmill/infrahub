from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class PersonWithCarsTransform(InfrahubTransform):
    query = "person_with_cars"

    async def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"name": data["TestingPerson"]["edges"][0]["node"]["name"]["value"]}
