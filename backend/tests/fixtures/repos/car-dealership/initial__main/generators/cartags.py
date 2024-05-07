from infrahub_sdk.generator import InfrahubGenerator


class Generator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        owner = data["TestingPerson"]["edges"][0]["node"]
        owner_name: str = owner["name"]["value"]
        for car in owner["cars"]["edges"]:
            car_name: str = car["node"]["name"]["value"]
            payload = {
                "name": f"{owner_name.lower()}-{car_name.lower()}",
                "description": "Tag",
            }
            obj = await self.client.create(kind="BuiltinTag", data=payload)
            await obj.save(allow_upsert=True)
