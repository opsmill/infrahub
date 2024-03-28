from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Union

from infrahub.core.constants import InfrahubKind
from infrahub.core.query import Query
from infrahub.core.registry import registry

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@dataclass
class IPPrefixData:
    id: UUID
    prefix: Union[ipaddress.IPv6Network, ipaddress.IPv4Network]


@dataclass
class IPAddressData:
    id: UUID
    address: Union[ipaddress.IPv6Interface, ipaddress.IPv4Interface]


class IPPrefixSubnetFetch(Query):
    name: str = "ipprefix_subnet_fetch"

    def __init__(self, ip_prefix, *args, **kwargs):
        self.ip_prefix = ip_prefix
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        query = """
        MATCH (pfx:%s)-[HAS_ATTRIBUTE]-(an:Attribute {name: "prefix"})-[HAS_VALUE]-(av:AttributeValue)
        """ % (InfrahubKind.IPPREFIX)

        self.add_to_query(query)
        self.return_labels = ["pfx", "av"]

    def get_container(self):
        """Return the more specific prefix that contains this one."""
        prefix = ipaddress.ip_network(self.ip_prefix.prefix.value)
        candidates: List[IPPrefixData] = []

        for result in self.get_results():
            candidate = IPPrefixData(
                id=result.get("pfx").get("uuid"), prefix=ipaddress.ip_network(result.get("av").get("value"))
            )
            if (
                prefix.version == candidate.prefix.version
                and prefix != candidate.prefix
                and prefix.subnet_of(candidate.prefix)
            ):
                candidates.append(candidate)

        container: Optional[IPPrefixData] = None
        for candidate in candidates:
            if not container or candidate.prefix.prefixlen > container.prefix.prefixlen:
                container = candidate
        return container

    def get_subnets(self):
        """Return a list of all subnets fitting in the prefix."""
        prefix = ipaddress.ip_network(self.ip_prefix.prefix.value)
        subnets: List[IPPrefixData] = []

        for result in self.get_results():
            subnet = IPPrefixData(
                id=result.get("pfx").get("uuid"), prefix=ipaddress.ip_network(result.get("av").get("value"))
            )
            if prefix.version == subnet.prefix.version and prefix != subnet.prefix and subnet.prefix.subnet_of(prefix):
                subnets.append(subnet)

        return subnets


class IPPrefixIPAddressFetch(Query):
    name: str = "ipprefix_ipaddress_fetch"

    def __init__(self, ip_prefix, *args, **kwargs):
        self.ip_prefix = ip_prefix
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        query = """
        MATCH (addr:%s)-[HAS_ATTRIBUTE]-(an:Attribute {name: "address"})-[HAS_VALUE]-(av:AttributeValue)
        """ % (InfrahubKind.IPADDRESS)

        self.add_to_query(query)
        self.return_labels = ["addr", "av"]

    def get_addresses(self):
        """Return a list of all addresses fitting in the prefix."""
        prefix = ipaddress.ip_network(self.ip_prefix.prefix.value)
        addresses: List[IPAddressData] = []

        for result in self.get_results():
            address = IPAddressData(
                id=result.get("addr").get("uuid"), address=ipaddress.ip_interface(result.get("av").get("value"))
            )
            if prefix.version == address.address.version and address.address in prefix:
                addresses.append(address)

        return addresses


async def get_container(
    ip_prefix, db: InfrahubDatabase, branch: Optional[Union[Branch, str]] = None, at=None
) -> List[str]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixSubnetFetch.init(db=db, branch=branch, ip_prefix=ip_prefix, at=at)
    await query.execute(db=db)
    return query.get_container()


async def get_subnets(
    ip_prefix, db: InfrahubDatabase, branch: Optional[Union[Branch, str]] = None, at=None
) -> List[str]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixSubnetFetch.init(db=db, branch=branch, ip_prefix=ip_prefix, at=at)
    await query.execute(db=db)
    return query.get_subnets()


async def get_ip_addresses(
    ip_prefix, db: InfrahubDatabase, branch: Optional[Union[Branch, str]] = None, at=None
) -> List[str]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixIPAddressFetch.init(db=db, branch=branch, ip_prefix=ip_prefix, at=at)
    await query.execute(db=db)
    return query.get_addresses()
