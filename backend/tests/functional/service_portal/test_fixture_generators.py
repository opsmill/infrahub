from __future__ import annotations

from ipaddress import ip_interface, ip_network
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.protocols import (
    CoreGeneratorDefinition,
    CoreGeneratorGroup,
    CoreGraphQLQuery,
    CoreIPAddressPool,
    CoreIPPrefixPool,
    CoreNumberPool,
)

from infrahub.core.constants import GeneratorInstanceStatus
from tests.helpers.test_app import TestInfrahubApp

from .conftest import (
    ACTIVATE_GENERATOR,
    ACTIVATE_TARGETS,
    ALLOCATE_GENERATOR,
    ALLOCATE_TARGETS,
    SERVICE_KIND,
    add_to_group,
    create_service,
    failed_run_messages,
    get_generator_instance,
    port_id,
    run_generator,
    service_port_ids,
)

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode

RUN_FAILURE = r"generator run failures"


async def create_targeted_service(client: InfrahubClient, branch: str, **data: Any) -> InfrahubNode:
    await client.branch.create(branch_name=branch)
    service = await create_service(client=client, branch=branch, name=branch, **data)
    await add_to_group(client=client, branch=branch, group_name=ALLOCATE_TARGETS, node_id=service.id)
    await add_to_group(client=client, branch=branch, group_name=ACTIVATE_TARGETS, node_id=service.id)
    return service


async def generated_objects(client: InfrahubClient, branch: str, service_id: str) -> dict[str, set[str]]:
    service = await client.get(kind=SERVICE_KIND, id=service_id, branch=branch, prefetch_relationships=True)
    groups = await client.filters(kind=CoreGeneratorGroup, branch=branch, include=["members"])
    return {
        "vlans": {node.id for node in await client.all(kind="IpamVLAN", branch=branch)},
        "prefixes": {node.id for node in await client.all(kind="IpamIPPrefix", branch=branch)},
        "addresses": {node.id for node in await client.all(kind="IpamIPAddress", branch=branch)},
        "service_peers": {
            service.vlan.id,
            service.prefix.id,
            service.gateway_ip_address.id,
            *await service_port_ids(client, branch, service_id),
        },
        "generator_group_members": {peer_id for group in groups for peer_id in group.members.peer_ids},
    }


class TestDedicatedInternetFixtureGenerators(TestInfrahubApp):
    async def test_import_registers_generators_schema_and_supporting_objects(
        self, dedicated_internet_repo: InfrahubNode, client: InfrahubClient
    ) -> None:
        definitions = await client.all(kind=CoreGeneratorDefinition, prefetch_relationships=True)
        queries = await client.all(kind=CoreGraphQLQuery)
        service_schema = await client.schema.get(kind=SERVICE_KIND, refresh=True)
        template_schema = await client.schema.get(kind=f"Template{SERVICE_KIND}")
        interfaces = await client.all(kind="DcimInterface")
        vlan_pool = await client.get(kind=CoreNumberPool, name__value="Customer vlan pool")
        prefix_pools = await client.all(kind=CoreIPPrefixPool)
        address_pools = await client.all(kind=CoreIPAddressPool)

        assert {
            (item.name.value, item.targets.peer.name.value, item.query.peer.name.value) for item in definitions
        } == {
            (ALLOCATE_GENERATOR, ALLOCATE_TARGETS, ALLOCATE_GENERATOR),
            (ACTIVATE_GENERATOR, ACTIVATE_TARGETS, ACTIVATE_GENERATOR),
        }
        assert {query.name.value for query in queries} == {ALLOCATE_GENERATOR, ACTIVATE_GENERATOR}
        assert set(service_schema.attribute_names) == {"name", "status", "bandwidth", "ip_package", "fail_generator"}
        assert set(service_schema.relationship_names) >= {
            "location",
            "dedicated_interfaces",
            "vlan",
            "gateway_ip_address",
            "prefix",
        }
        assert template_schema.kind == f"Template{SERVICE_KIND}"
        assert {site.name.value for site in await client.all(kind="LocationSite")} == {"site-a", "site-b"}
        assert {tuple(interface.hfid) for interface in interfaces} == {
            ("core-a1", "port-1"),
            ("core-a1", "port-2"),
            ("core-b1", "port-1"),
        }
        assert (vlan_pool.node.value, vlan_pool.node_attribute.value) == ("IpamVLAN", "vlan_id")
        assert [(pool.name.value, pool.default_prefix_length.value) for pool in prefix_pools] == [
            ("Customer prefixes pool", 29)
        ]
        assert [pool.name.value for pool in address_pools] == ["Management IP pool"]

    async def test_generators_in_order_produce_active_service(
        self, dedicated_internet_repo: InfrahubNode, client: InfrahubClient
    ) -> None:
        branch = "svc-in-order"
        service = await create_targeted_service(client=client, branch=branch)

        await run_generator(client=client, branch=branch, definition_name=ALLOCATE_GENERATOR, node_id=service.id)
        await run_generator(client=client, branch=branch, definition_name=ACTIVATE_GENERATOR, node_id=service.id)

        result = await client.get(kind=SERVICE_KIND, id=service.id, branch=branch, prefetch_relationships=True)
        assert result.status.value == "active"
        assert 1000 <= result.vlan.peer.vlan_id.value <= 2000
        assert result.prefix.peer.prefix.value.prefixlen == 29
        assert result.prefix.peer.prefix.value.subnet_of(ip_network("203.0.113.0/24"))
        assert ip_interface(result.gateway_ip_address.peer.address.value).ip in ip_network("172.16.1.0/24")
        assert await service_port_ids(client, branch, service.id) == [
            await port_id(client, branch, "core-a1", "port-1")
        ]
        for definition_name in (ALLOCATE_GENERATOR, ACTIVATE_GENERATOR):
            instance = await get_generator_instance(client, branch, definition_name, service.id)
            assert instance.status.value == GeneratorInstanceStatus.READY.value

    async def test_activate_before_allocate_fails_on_missing_vlan(
        self, dedicated_internet_repo: InfrahubNode, client: InfrahubClient
    ) -> None:
        branch = "svc-out-of-order"
        service = await create_targeted_service(client=client, branch=branch)

        with pytest.raises(GraphQLError, match=RUN_FAILURE):
            await run_generator(client=client, branch=branch, definition_name=ACTIVATE_GENERATOR, node_id=service.id)

        instance = await get_generator_instance(client, branch, ACTIVATE_GENERATOR, service.id)
        result = await client.get(kind=SERVICE_KIND, id=service.id, branch=branch)
        assert instance.status.value == GeneratorInstanceStatus.ERROR.value
        assert await failed_run_messages(instance.id) == [
            "Flow run encountered an exception: ValueError: "
            f"Service {branch} has no VLAN, run dedicated_internet_allocate first"
        ]
        assert result.status.value == "draft"

        await run_generator(client=client, branch=branch, definition_name=ALLOCATE_GENERATOR, node_id=service.id)
        await run_generator(client=client, branch=branch, definition_name=ACTIVATE_GENERATOR, node_id=service.id)

        result = await client.get(kind=SERVICE_KIND, id=service.id, branch=branch)
        assert result.status.value == "active"

    async def test_failure_flag_puts_activate_instance_in_error(
        self, dedicated_internet_repo: InfrahubNode, client: InfrahubClient
    ) -> None:
        branch = "svc-failing"
        service = await create_targeted_service(client=client, branch=branch, fail_generator=True)
        await run_generator(client=client, branch=branch, definition_name=ALLOCATE_GENERATOR, node_id=service.id)

        with pytest.raises(GraphQLError, match=RUN_FAILURE):
            await run_generator(client=client, branch=branch, definition_name=ACTIVATE_GENERATOR, node_id=service.id)

        instance = await get_generator_instance(client, branch, ACTIVATE_GENERATOR, service.id)
        assert instance.status.value == GeneratorInstanceStatus.ERROR.value
        assert await failed_run_messages(instance.id) == [
            f"Flow run encountered an exception: RuntimeError: Service {branch} is set to fail the generator"
        ]

    async def test_rerunning_generators_leaves_generated_objects_unchanged(
        self, dedicated_internet_repo: InfrahubNode, client: InfrahubClient
    ) -> None:
        branch = "svc-rerun"
        service = await create_targeted_service(client=client, branch=branch)
        await run_generator(client=client, branch=branch, definition_name=ALLOCATE_GENERATOR, node_id=service.id)
        await run_generator(client=client, branch=branch, definition_name=ACTIVATE_GENERATOR, node_id=service.id)
        before = await generated_objects(client=client, branch=branch, service_id=service.id)

        await run_generator(client=client, branch=branch, definition_name=ALLOCATE_GENERATOR, node_id=service.id)
        await run_generator(client=client, branch=branch, definition_name=ACTIVATE_GENERATOR, node_id=service.id)

        after = await generated_objects(client=client, branch=branch, service_id=service.id)
        assert after == before
        assert len(before["service_peers"]) == 4
        assert len(before["generator_group_members"]) == 3
