"""IP prefixes and resource pools slice.

Faithful transcription of the "Create IP Prefixes" / "Create Pool IPv6
prefixes" / "Create IPv6 IP from IPv6 Prefix pool" section of ``run()`` in
``models/infrastructure_edge.py`` (lines ~2626-2770) plus the network
constants it uses (lines ~557-565). The allocation order and the
save/``allow_upsert`` mix are preserved call by call: downstream tests assert
the deterministic next-free values (172.16.0.31/16 from the management pool,
203.111.0.248/29 from the external pool) and the exact prefix tree
(10.0.0.0/16 loopbacks, 10.1.0.0/16 interconnections, 10.2.0.0/16 left
empty, and the six sequential /110 IPv6 prefixes).
"""

from __future__ import annotations

from ipaddress import IPv4Network, IPv6Network
from typing import TYPE_CHECKING

import pytest

from data.common import save_with_retry
from data.handles import IpamPoolsHandle

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from data.handles import RbacHandle

NETWORKS_SUPERNET = IPv4Network("10.0.0.0/8")
NETWORKS_SUPERNET_IPV6 = IPv6Network("2001:DB8::/100")
MANAGEMENT_NETWORKS = IPv4Network("172.16.0.0/16")

# Here with current logic we allocate 3 /29 per edge device
# We have max 10 edges on a single site, max 200 sites
# 3*10*200 = 6000 -> we need to be able to fit 6000 /29
# Thus we need a /16
NETWORKS_POOL_EXTERNAL_SUPERNET = IPv4Network("203.111.0.0/16")


@pytest.fixture(scope="session")
async def data_ipam_pools(  # noqa: PLR0914  (transcribed script section, one local per created node)
    data_client: InfrahubClient,
    schema_base: None,
    data_rbac: RbacHandle,
    infrahub_provisioned_externally: bool,
) -> IpamPoolsHandle:
    """Seed the supernets, the six resource pools and the IPv6 addresses.

    Depends on ``data_rbac`` because every IPv6 address carries the
    ``pop-builder`` account id as its ``source`` metadata, exactly like the
    script (which read it back from ``client.store``).
    """
    if infrahub_provisioned_externally:
        return IpamPoolsHandle.external()

    branch = "main"
    account_pop_id = data_rbac.accounts["pop-builder"]

    default_ip_namespace = await data_client.get(kind="IpamNamespace", name__value="default")

    # Creating IP Core Supernet and Pool
    supernet_prefix = await data_client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(NETWORKS_SUPERNET), member_type="prefix"
    )
    await supernet_prefix.save()
    supernet_pool = await data_client.create(
        kind="CoreIPPrefixPool",
        name="Internal networks pool",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=16,
        ip_namespace=default_ip_namespace,
        resources=[supernet_prefix],
        branch=branch,
    )
    # Using upsert for branch agnostic nodes in order to execute the script in different branches during development
    await supernet_pool.save(allow_upsert=True)

    # Creating IP Loopback Prefix and Pool
    loopback_prefix = await data_client.allocate_next_ip_prefix(
        resource_pool=supernet_pool, member_type="address", branch=branch
    )
    loopback_pool = await data_client.create(
        kind="CoreIPAddressPool",
        name="Loopbacks pool",
        default_address_type="IpamIPAddress",
        default_prefix_length=32,
        ip_namespace=default_ip_namespace,
        resources=[loopback_prefix],
        branch=branch,
    )
    await loopback_pool.save(allow_upsert=True)

    # Creating IP Interconnection Prefix and Pool
    # NB: `kind` is typing-only sugar on allocate_next_ip_prefix (unused at runtime); mirrored from the script.
    interconnection_prefix = await data_client.allocate_next_ip_prefix(
        kind="IpamIPPrefix",  # type: ignore[call-overload]
        resource_pool=supernet_pool,
        branch=branch,
    )
    interconnection_pool = await data_client.create(
        kind="CoreIPPrefixPool",
        name="Interconnections pool",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=31,
        default_member_type="address",
        ip_namespace=default_ip_namespace,
        resources=[interconnection_prefix],
        branch=branch,
    )
    await interconnection_pool.save(allow_upsert=True)

    # Allocate an empty prefix (the script discards the return; the prefix — 10.2.0.0/16 —
    # stays in the tree, deliberately empty and unused)
    empty_prefix = await data_client.allocate_next_ip_prefix(resource_pool=supernet_pool, branch=branch)

    # Creating IP Management Prefix and Pool
    management_prefix = await data_client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(MANAGEMENT_NETWORKS), member_type="address"
    )
    await management_prefix.save(allow_upsert=True)
    management_pool = await data_client.create(
        kind="CoreIPAddressPool",
        name="Management addresses pool",
        default_address_type="IpamIPAddress",
        default_prefix_length=16,
        ip_namespace=default_ip_namespace,
        resources=[management_prefix],
        branch=branch,
    )
    await management_pool.save(allow_upsert=True)

    # Creating IP External Supernet and Pool
    external_supernet = await data_client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(NETWORKS_POOL_EXTERNAL_SUPERNET), member_type="prefix"
    )
    await external_supernet.save()
    external_pool = await data_client.create(
        kind="CoreIPPrefixPool",
        name="External prefixes pool",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=29,
        default_member_type="address",
        ip_namespace=default_ip_namespace,
        resources=[external_supernet],
        branch=branch,
    )
    await external_pool.save(allow_upsert=True)

    # Creating IPv6 Core Supernet and Pool
    ipv6_supernet_prefix = await data_client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(NETWORKS_SUPERNET_IPV6), member_type="prefix"
    )
    await ipv6_supernet_prefix.save()
    ipv6_supernet_pool = await data_client.create(
        kind="CoreIPPrefixPool",
        name="Internal networks pool (IPv6)",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=110,
        default_member_type="address",
        ip_namespace=default_ip_namespace,
        resources=[ipv6_supernet_prefix],
        branch=branch,
    )
    await ipv6_supernet_pool.save(allow_upsert=True)

    # Creating pool IPv6 Prefixes and IPs: six sequential /110 allocations
    # (the script spells out six identical calls)
    ipv6_internal_networks = [
        await data_client.allocate_next_ip_prefix(
            resource_pool=ipv6_supernet_pool,
            kind="IpamIPPrefix",  # type: ignore[call-overload]
            branch=branch,
        )
        for _ in range(6)
    ]

    # Create IPv6 IP from IPv6 Prefix pool
    ipv6_addresses = []
    for index, network in enumerate(ipv6_internal_networks[:4]):
        multiplier = index + 1
        host_list = list(network.prefix.value.hosts())
        number_of_hosts = min(multiplier * 17, len(host_list))
        ipv6_addresses.extend(host_list[:number_of_hosts])

    batch = await data_client.create_batch()
    for ipv6_addr in ipv6_addresses:
        obj = await data_client.create(
            branch=branch, kind="IpamIPAddress", address={"value": ipv6_addr, "source": account_pop_id}
        )
        batch.add(task=save_with_retry, node=obj, obj=obj)
    async for _, _response in batch.execute():
        pass

    return IpamPoolsHandle(
        pools={
            "Internal networks pool": supernet_pool.id,
            "Loopbacks pool": loopback_pool.id,
            "Interconnections pool": interconnection_pool.id,
            "Management addresses pool": management_pool.id,
            "External prefixes pool": external_pool.id,
            "Internal networks pool (IPv6)": ipv6_supernet_pool.id,
        },
        prefixes={
            str(NETWORKS_SUPERNET): supernet_prefix.id,
            str(loopback_prefix.prefix.value): loopback_prefix.id,
            str(interconnection_prefix.prefix.value): interconnection_prefix.id,
            str(empty_prefix.prefix.value): empty_prefix.id,
            str(MANAGEMENT_NETWORKS): management_prefix.id,
            str(NETWORKS_POOL_EXTERNAL_SUPERNET): external_supernet.id,
            str(NETWORKS_SUPERNET_IPV6): ipv6_supernet_prefix.id,
        },
    )
