import re

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


async def test_get_resource_prefix_type_of_the_peer_generic_is_rejected(
    db: InfrahubDatabase, default_branch: Branch, kind_override_prefix_pool: CoreIPPrefixPool
) -> None:
    """A generic is not allocatable, including when it is the peer kind itself."""
    with pytest.raises(
        ValidationError,
        match=re.escape(f"{InfrahubKind.IPPREFIX!r} is not a valid kind to allocate for {InfrahubKind.IPPREFIX!r}"),
    ) as exc:
        await kind_override_prefix_pool.get_resource(
            db=db, branch=default_branch, prefix_type=InfrahubKind.IPPREFIX, peer_kind=InfrahubKind.IPPREFIX
        )

    assert "IpamIPPrefix" in str(exc.value)


async def test_get_resource_address_type_of_the_peer_generic_is_rejected(
    db: InfrahubDatabase, default_branch: Branch, kind_override_address_pool: CoreIPAddressPool
) -> None:
    """A generic is not allocatable, including when it is the peer kind itself."""
    with pytest.raises(
        ValidationError,
        match=re.escape(f"{InfrahubKind.IPADDRESS!r} is not a valid kind to allocate for {InfrahubKind.IPADDRESS!r}"),
    ) as exc:
        await kind_override_address_pool.get_resource(
            db=db, branch=default_branch, address_type=InfrahubKind.IPADDRESS, peer_kind=InfrahubKind.IPADDRESS
        )

    assert "IpamIPAddress" in str(exc.value)
