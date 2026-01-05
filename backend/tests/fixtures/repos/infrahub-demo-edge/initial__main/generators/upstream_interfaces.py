from infrahub_sdk.generator import InfrahubGenerator

#   In this Generator: We are forcing the InterfaceL3 description
#   If there is a InfraCircuit Connected on it
#   If the InterfaceL3 status is provisioning


class Generator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        # Extract the first node in the 'InfraInterfaceL3' edges array
        upstream_interface = data["InfraInterfaceL3"]["edges"][0]["node"]

        # Set local variables to easier manipulation
        provider = None
        vendor_id = None
        role: str = upstream_interface["role"]["value"]
        status: str = upstream_interface["status"]["value"]
        speed: int = upstream_interface["speed"]["value"] / 1000

        if status != "provisioning":
            return  # We enforce it only on new interfaces to avoid "noise"

        # Check and extract data from the connected endpoint
        if "connected_endpoint" in upstream_interface and "node" in upstream_interface["connected_endpoint"]:
            connected_endpoint = upstream_interface["connected_endpoint"]["node"]
            if "circuit" in connected_endpoint and "node" in connected_endpoint["circuit"]:
                circuit = connected_endpoint["circuit"]["node"]
                if "provider" in circuit and "node" in circuit["provider"]:
                    provider = circuit["provider"]["node"]["name"]["value"]
                if "vendor_id" in circuit:
                    vendor_id = circuit["vendor_id"]["value"]

        # Update the object description if provider and vendor_id are available
        if provider and vendor_id:
            new_description = f"{role.upper()}: ({provider.upper()}x{vendor_id.upper()}) [{speed}Gbps]"
            # Retrieve the object based on type and ID, then update its description
            obj = await self.client.get(kind=upstream_interface["__typename"], id=upstream_interface["id"])
            obj.description.value = new_description
            await obj.save(allow_upsert=True)
