"""Data seed for the pool "default target kind" override demo.

Creates the two resource pools the demo schema needs, both defaulting to the Ipam kinds so an
allocation can override them with the Infra siblings.

Usage::

    infrahubctl schema load models/base models/examples/ipam_kind_override.yml
    infrahubctl run models/examples/ipam_kind_override_data.py
"""

import logging
from ipaddress import IPv4Network

from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import CoreIPAddressPool, CoreIPPrefixPool, IpamNamespace

DEMO_SUPERNET = IPv4Network("198.51.100.0/24")
ADDRESS_POOL_RESOURCE_PREFIX_LENGTH = 25


async def run(client: InfrahubClient, log: logging.Logger, branch: str) -> None:
    branch = branch or "main"

    default_ip_namespace = await client.get(kind=IpamNamespace, name__value="default", branch=branch)

    log.info("Creating Kind override demo supernet")
    supernet_prefix = await client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(DEMO_SUPERNET), member_type="prefix"
    )
    # Using upsert so the script can be re-run on the same branch during development.
    await supernet_prefix.save(allow_upsert=True)

    log.info("Creating Kind override demo prefix pool")
    prefix_pool = await client.create(
        kind=CoreIPPrefixPool,
        name="Kind override demo prefix pool",
        description="Defaults to IpamIPPrefix — pick InfraTransitPrefix at allocation time to see the override",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=29,
        default_member_type="address",
        ip_namespace=default_ip_namespace,
        resources=[supernet_prefix],
        branch=branch,
    )
    await prefix_pool.save(allow_upsert=True)

    log.info("Allocating an address-pool resource prefix from the prefix pool")
    # /25 rather than the pool's /29 default: 8 addresses is too few to try the override out by hand.
    address_pool_resource = await client.allocate_next_ip_prefix(
        resource_pool=prefix_pool,
        prefix_type="IpamIPPrefix",
        member_type="address",
        prefix_length=ADDRESS_POOL_RESOURCE_PREFIX_LENGTH,
        branch=branch,
    )

    log.info("Creating Kind override demo address pool")
    address_pool = await client.create(
        kind=CoreIPAddressPool,
        name="Kind override demo address pool",
        description="Defaults to IpamIPAddress — pick InfraLoopbackAddress at allocation time to see the override",
        default_address_type="IpamIPAddress",
        default_prefix_length=32,
        ip_namespace=default_ip_namespace,
        resources=[address_pool_resource],
        branch=branch,
    )
    await address_pool.save(allow_upsert=True)

    log.info("Creating Kind override demo object")
    demo_object = await client.create(
        branch=branch,
        kind="InfraKindOverrideDemo",
        name="kind-override-demo",
    )
    await demo_object.save(allow_upsert=True)

    log.info(
        "Done. Allocate from 'Kind override demo prefix pool' / 'Kind override demo address pool' "
        "or set the relationships on 'kind-override-demo' (InfraKindOverrideDemo) and pick "
        "InfraTransitPrefix / InfraLoopbackAddress to exercise the default target kind override."
    )
