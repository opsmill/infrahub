from infrahub_sdk.generator import InfrahubGenerator

#   In this Generator: We want to create 2 InfraCircuitEndpoints (A & Z)
#   If the InfraCircuit doesn't have any CircuitEndpoints


class Generator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        # Extract the first node in the 'InfraCircuit' edges array
        circuits = data["InfraCircuit"]["edges"]

        for circuit in circuits:
            # There is already endpoints, no need to add more :)
            if circuit["node"]["endpoints"]["count"] != 0:
                continue

            # Set local variables to easier manipulation
            id = circuit["node"]["id"]
            provider = circuit["node"]["provider"]["node"]["name"]["value"]
            circuit_id: str = circuit["node"]["circuit_id"]["value"]
            vendor_id: str = circuit["node"]["vendor_id"]["value"]

            # Manage description
            description: str = f"{circuit_id} - ({provider.upper()}{' x '+vendor_id.upper() if vendor_id else ''})"

            for i in range(1, 3):
                data = {
                    "circuit": {"id": id},
                    "description": {"value": description},
                }
                if i == 1:
                    description += " - A Side"
                elif i == 2:
                    description += " - Z Side"

                obj = await self.client.create(kind="InfraCircuitEndpoint", data=data)
                await obj.save(allow_upsert=True)
