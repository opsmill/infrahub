from infrahub_sdk.generator import InfrahubGenerator
from infrahub_sdk.node import Attribute


class DedicatedInternetActivate(InfrahubGenerator):
    """Assign a port at the service's location and mark the service active; requires the allocated VLAN."""

    async def generate(self, data: dict) -> None:
        service_data = data["ServiceDedicatedInternet"]["edges"][0]["node"]
        service_id: str = service_data["id"]
        name: str = service_data["name"]["value"]

        if not service_data["vlan"]["node"]:
            raise ValueError(f"Service {name} has no VLAN, run dedicated_internet_allocate first")
        if service_data["fail_generator"]["value"]:
            raise RuntimeError(f"Service {name} is set to fail the generator")

        location = service_data["location"]["node"]
        candidates = [
            (interface["node"]["service"]["node"], device["node"]["name"]["value"], interface["node"])
            for device in location["devices"]["edges"]
            for interface in device["node"]["interfaces"]["edges"]
        ]
        # The port already assigned to this service first (idempotent re-runs), then the first free one.
        ports = sorted(
            ((owner, device, port) for owner, device, port in candidates if owner is None or owner["id"] == service_id),
            key=lambda item: (item[0] is None, item[1], item[2]["name"]["value"]),
        )
        if not ports:
            raise RuntimeError(f"No free port at {location['name']['value']} for service {name}")

        # Port and service are inventory, not generated objects: keep them out of the tracking group
        # so its cleanup never deletes them.
        port = await self.client.get(kind="DcimInterface", id=ports[0][2]["id"])
        port.service = service_id
        await port.save(update_group_context=False)

        service = await self.client.get(kind="ServiceDedicatedInternet", id=service_id)
        status = service.status
        assert isinstance(status, Attribute)
        status.value = "active"
        await service.save(update_group_context=False)
