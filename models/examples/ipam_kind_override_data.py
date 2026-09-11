"""IFC-2764 — data seed for the pool "default target kind" override demo.

Companion data script for ``models/examples/ipam_kind_override.yml``. That
schema adds a second concrete kind per IPAM generic (``InfraLoopbackAddress``
inheriting ``BuiltinIPAddress``, ``InfraTransitPrefix`` inheriting
``BuiltinIPPrefix``) plus a ``InfraKindOverrideDemo`` node whose
relationships peer at the bare generics. Pools are data, not schema, so this
script creates the two resource pools needed to actually exercise the
override in the UI:

- ``CoreIPPrefixPool`` with ``default_prefix_type=IpamIPPrefix``
- ``CoreIPAddressPool`` with ``default_address_type=IpamIPAddress``

Both default to the ``Ipam`` kind defined in ``models/base/ipam.yml`` — the
whole point of the demo is to allocate from these pools and pick
``InfraTransitPrefix`` / ``InfraLoopbackAddress`` instead, and see the
override take effect.

Modelled on the "Create IP Prefixes" / "Create Pool IPv6 prefixes" section
of ``run()`` in ``models/infrastructure_edge.py`` and on
``tests/e2e/data/ipam_pools.py``.

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

    log.info("Creating IFC-2764 demo supernet")
    supernet_prefix = await client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(DEMO_SUPERNET), member_type="prefix"
    )
    # Using upsert so the script can be re-run on the same branch during development.
    await supernet_prefix.save(allow_upsert=True)

    log.info("Creating IFC-2764 demo prefix pool")
    prefix_pool = await client.create(
        kind=CoreIPPrefixPool,
        name="IFC-2764 demo prefix pool",
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
    # Explicitly a /25 rather than the prefix pool's /29 default: the address pool is meant to
    # be allocated from by hand while trying the override out, and a /29 gives only 8 addresses
    # before it is exhausted. The /24 supernet keeps plenty of room for prefix allocations.
    address_pool_resource = await client.allocate_next_ip_prefix(
        resource_pool=prefix_pool,
        prefix_type="IpamIPPrefix",
        member_type="address",
        prefix_length=ADDRESS_POOL_RESOURCE_PREFIX_LENGTH,
        branch=branch,
    )

    log.info("Creating IFC-2764 demo address pool")
    address_pool = await client.create(
        kind=CoreIPAddressPool,
        name="IFC-2764 demo address pool",
        description="Defaults to IpamIPAddress — pick InfraLoopbackAddress at allocation time to see the override",
        default_address_type="IpamIPAddress",
        default_prefix_length=32,
        ip_namespace=default_ip_namespace,
        resources=[address_pool_resource],
        branch=branch,
    )
    await address_pool.save(allow_upsert=True)

    log.info("Creating IFC-2764 demo object")
    demo_object = await client.create(
        branch=branch,
        kind="InfraKindOverrideDemo",
        name="ifc-2764-demo",
    )
    await demo_object.save(allow_upsert=True)

    log.info(
        "Done. Allocate from 'IFC-2764 demo prefix pool' / 'IFC-2764 demo address pool' "
        "or set the relationships on 'ifc-2764-demo' (InfraKindOverrideDemo) and pick "
        "InfraTransitPrefix / InfraLoopbackAddress to exercise the default target kind override."
    )
