from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class ConvertedPersonWith(InfrahubTransform):
    query = "person_with_cars"

    async def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        node_id = data["TestingPerson"]["edges"][0]["node"]["id"]

        person = self.store.get(key=node_id, kind="TestingPerson", raise_when_missing=False)
        if not person:
            person = await self.client.get(kind="TestingPerson", id=node_id)

        return {"name": person.name.value, "age": person.age.value}
