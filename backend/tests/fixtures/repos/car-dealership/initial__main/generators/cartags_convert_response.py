from infrahub_sdk.generator import InfrahubGenerator


class Generator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        owner = self.nodes[0]
        for node in owner.cars.peers:
            car = node.peer
            payload = {
                "name": f"InfrahubNode-{owner.name.value.lower()}-{car.name.value.lower()}",
                "description": "Tag",
            }
            obj = await self.client.create(kind="BuiltinTag", data=payload)
            await obj.save(allow_upsert=True)
