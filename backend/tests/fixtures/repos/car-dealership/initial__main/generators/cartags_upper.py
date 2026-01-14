from infrahub_sdk.generator import InfrahubGenerator


class Generator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        """
        This generator creates a tag in UPPERCASE for each owner<>tag association
        """
        owner = data["TestingPerson"]["edges"][0]["node"]
        owner_name: str = owner["name"]["value"]
        for car in owner["cars"]["edges"]:
            car_name: str = car["node"]["name"]["value"]
            payload = {
                "name": f"{owner_name.upper()}__{car_name.upper()}",
                "description": "Tag",
            }
            obj = await self.client.create(kind="TestingTag", data=payload)
            await obj.save(allow_upsert=True)
