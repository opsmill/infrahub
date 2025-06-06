from infrahub_sdk.generator import InfrahubGenerator
import logging

async def find_interface(client, site_id):
    # Retrieve all 'edge' router from the site
    devices = await client.filters(kind="InfraDevice", role__value="edge", site__ids=[site_id])

    if len(devices) == 0:
        raise ValueError("Couldn't find devices")

    # Take the first one of the list
    device = devices[0]

    # Retrieve all L3 interfaces from this Device with 'backbone' role
    interfaces = await client.filters(
        kind="InfraInterfaceL3",
        device__ids=[device.id],
        role__value="backbone",
        include=["connected_endpoint", "ip_addresses", "device"],
        prefetch_relationships=True,
        populate_store=True
    )

    if len(interfaces) == 0:
        raise ValueError("Couldn't find interfaces")

    # Return the first one of the list
    return interfaces[0]


class Generator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        log = logging.getLogger("infrahub.tasks")
        service_id = data["InfraBackBoneService"]["edges"][0]["node"]["id"]
        service_name = data["InfraBackBoneService"]["edges"][0]["node"]["name"]["value"]
        circuit_id = data["InfraBackBoneService"]["edges"][0]["node"]["circuit_id"]["value"]
        internal_circuit_id = data["InfraBackBoneService"]["edges"][0]["node"]["internal_circuit_id"]["value"]
        site_a_id = data["InfraBackBoneService"]["edges"][0]["node"]["site_a"]["node"]["id"]
        site_b_id = data["InfraBackBoneService"]["edges"][0]["node"]["site_b"]["node"]["id"]
        provider_id = data["InfraBackBoneService"]["edges"][0]["node"]["provider"]["node"]["id"]

        # Create Circuit
        log.info("Create Circuit")
        circuit = await self.client.create(
            kind="InfraCircuit",
            provider={"id": provider_id},
            vendor_id=circuit_id,
            circuit_id=internal_circuit_id,
            status="active",
            role="backbone",
        )

        await circuit.save(allow_upsert=True)

        # Retrieve one interface per Site to be use for Circuit Endpoints
        log.info("Retrieve one interface per Site to be use for Circuit Endpoints")
        interface_a = await find_interface(self.client, site_a_id)
        interface_b = await find_interface(self.client, site_b_id)

        # Assign the 2 Interfaces as Circuit Endpoints
        log.info("Assign the 2 Interfaces as Circuit Endpoints")
        if not interface_a.connected_endpoint.initialized:
            connected_endpoint_a = await self.client.create(
                kind="InfraCircuitEndpoint", circuit=circuit, site=site_a_id, connected_endpoint=interface_a
            )
            await connected_endpoint_a.save(allow_upsert=True)
        else:
            await interface_a.connected_endpoint.fetch()

            if (
                not interface_a.connected_endpoint.typename == "InfraCircuitEndpoint"
                or not interface_a.connected_endpoint.peer.circuit.id == circuit.id
            ):
                raise ValueError(f"{interface_a.name.value} on {interface_a.device.peer.name.value} is already connected!")

        if not interface_b.connected_endpoint.initialized:
            connected_endpoint_b = await self.client.create(
                kind="InfraCircuitEndpoint", circuit=circuit, site=site_b_id, connected_endpoint=interface_b
            )
            await connected_endpoint_b.save(allow_upsert=True)
        else:
            await interface_b.connected_endpoint.fetch()

            if (
                not interface_b.connected_endpoint.typename == "InfraCircuitEndpoint"
                or not interface_b.connected_endpoint.peer.circuit.id == circuit.id
            ):
                raise ValueError(f"{interface_b.name.value} on {interface_b.device.peer.name.value} is already connected!")


        # Retrieve Pool for interconnection subnets
        log.info("Retrieve Pool for interconnection subnets")
        internal_networks_pool = await self.client.get(kind="CoreIPPrefixPool", name__value="Internal networks pool")

        # Allocate the next free IP prefix for the service
        log.info("Allocate the next free IP prefix for the service")
        prefix = await self.client.allocate_next_ip_prefix(
            resource_pool=internal_networks_pool,
            prefix_length=31,
            member_type="address",
            data={"is_pool": True},
            identifier=f"{service_name}-{service_id}",
        )
        await prefix.save(allow_upsert=True)

        # Create a new Address Pool for this prefix
        log.info("Create a new Address Pool for this prefix")
        circuit_address_pool = await self.client.create(
            kind="CoreIPAddressPool",
            name=f"{service_name}-{service_id}",
            default_address_type="IpamIPAddress",
            default_prefix_size=31,
            resources=[prefix],
            is_pool=True,
            ip_namespace={"id": "default"},
        )
        await circuit_address_pool.save(allow_upsert=True)

        # Use the new pool to allocate 2 IPs on the interfaces
        log.info("Use the new pool to allocate 2 IPs on the interfaces")
        interface_a_ip = await self.client.allocate_next_ip_address(
            resource_pool=circuit_address_pool,
        )
        interface_a.ip_addresses.add(interface_a_ip)
        await interface_a.save(allow_upsert=True)

        interface_b_ip = await self.client.allocate_next_ip_address(
            resource_pool=circuit_address_pool,
        )
        interface_b.ip_addresses.add(interface_b_ip)
        await interface_b.save(allow_upsert=True)

        log.info("Execution finishes with success")
