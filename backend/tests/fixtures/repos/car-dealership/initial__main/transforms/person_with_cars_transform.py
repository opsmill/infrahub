from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class PersonWithCarsTransform(InfrahubTransform):
    query = "person_with_cars"
    timeout = 2

    async def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        if data["TestingPerson"]["edges"]:
            return {"name": data["TestingPerson"]["edges"][0]["node"]["name"]["value"]}

        return {"name": None}
