from infrahub_sdk.generator import InfrahubGenerator

#   In this Generator: We want to drained the BGP Sessions linked to an InfraCircuit
#   If the InfraCircuit Status is maintenance:
#       - We are changing the status of the BGP Sessions to maintenance


class Generator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        # Extract the first node in the 'InfraInterfaceL3' edges array
        circuits = data["InfraCircuit"]["edges"]

        for circuit in circuits:
            id = circuit["node"]["id"]
            status: str = circuit["node"]["status"]["value"]

            if status != "maintenance":
                continue  # No need to change the status of the BGP Sessions

            if circuit["node"]["bgp_sessions"]["count"] == 0:
                continue  # There is no BGP Sessions associated with this circuit

            bgp_sessions = circuit["node"]["bgp_sessions"]["edges"]
            for bgp_session in bgp_sessions:
                obj = await self.client.get(kind=bgp_session["node"]["__typename"], id=bgp_session["node"]["id"])
                obj.status.value = "maintenance"
                await obj.save(allow_upsert=True)
