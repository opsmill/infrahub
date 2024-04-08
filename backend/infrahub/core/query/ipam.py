from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, List, Optional, Union

from infrahub.core.constants import InfrahubKind
from infrahub.core.query import Query
from infrahub.core.registry import registry

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
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

    def __init__(self, ip_prefix: Union[ipaddress.IPv6Network, ipaddress.IPv4Network], *args, **kwargs):
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
        candidates: List[IPPrefixData] = []

        for result in self.get_results():
            candidate = IPPrefixData(
                id=result.get("pfx").get("uuid"), prefix=ipaddress.ip_network(result.get("av").get("value"))
            )
            if (
                self.ip_prefix.version == candidate.prefix.version
                and self.ip_prefix != candidate.prefix
                and self.ip_prefix.subnet_of(candidate.prefix)
            ):
                candidates.append(candidate)

        container: Optional[IPPrefixData] = None
        for candidate in candidates:
            if not container or candidate.prefix.prefixlen > container.prefix.prefixlen:
                container = candidate
        return container

    def get_subnets(self):
        """Return a list of all subnets fitting in the prefix."""
        subnets: List[IPPrefixData] = []

        for result in self.get_results():
            subnet = IPPrefixData(
                id=result.get("pfx").get("uuid"), prefix=ipaddress.ip_network(result.get("av").get("value"))
            )
            if (
                self.ip_prefix.version == subnet.prefix.version
                and self.ip_prefix != subnet.prefix
                and subnet.prefix.subnet_of(self.ip_prefix)
            ):
                subnets.append(subnet)

        return subnets


class IPPrefixIPAddressFetch(Query):
    name: str = "ipprefix_ipaddress_fetch"

    def __init__(self, ip_prefix: Union[ipaddress.IPv6Network, ipaddress.IPv4Network], *args, **kwargs):
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
        addresses: List[IPAddressData] = []

        for result in self.get_results():
            address = IPAddressData(
                id=result.get("addr").get("uuid"), address=ipaddress.ip_interface(result.get("av").get("value"))
            )
            if self.ip_prefix.version == address.address.version and address.address in self.ip_prefix:
                addresses.append(address)

        return addresses


class IPAddressIPPrefixFetch(Query):
    name: str = "ipaddress_ipprefix_fetch"

    def __init__(self, ip_address: Union[ipaddress.IPv6Interface, ipaddress.IPv4Interface], *args, **kwargs):
        self.ip_address = ip_address
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        query = """
        MATCH (pfx:%s)-[HAS_ATTRIBUTE]-(an:Attribute {name: "prefix"})-[HAS_VALUE]-(av:AttributeValue)
        """ % (InfrahubKind.IPPREFIX)

        self.add_to_query(query)
        self.return_labels = ["pfx", "av"]

    def get_prefix_for_address(self):
        """Return the more specific prefix that contains this address."""
        candidates: List[IPPrefixData] = []

        for result in self.get_results():
            candidate = IPPrefixData(
                id=result.get("pfx").get("uuid"), prefix=ipaddress.ip_network(result.get("av").get("value"))
            )
            if self.ip_address.version == candidate.prefix.version and self.ip_address in candidate.prefix:
                candidates.append(candidate)

        prefix: Optional[IPPrefixData] = None
        for candidate in candidates:
            if not prefix or candidate.prefix.prefixlen > prefix.prefix.prefixlen:
                prefix = candidate
        return prefix


async def get_container(
    ip_prefix: Union[ipaddress.IPv6Network, ipaddress.IPv4Network],
    db: InfrahubDatabase,
    branch: Optional[Union[Branch, str]] = None,
    at=None,
) -> IPPrefixData:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixSubnetFetch.init(db=db, branch=branch, ip_prefix=ip_prefix, at=at)
    await query.execute(db=db)
    return query.get_container()


async def get_subnets(
    ip_prefix: Union[ipaddress.IPv6Network, ipaddress.IPv4Network],
    db: InfrahubDatabase,
    branch: Optional[Union[Branch, str]] = None,
    at=None,
) -> Iterable[IPPrefixData]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixSubnetFetch.init(db=db, branch=branch, ip_prefix=ip_prefix, at=at)
    await query.execute(db=db)
    return query.get_subnets()


async def get_ip_addresses(
    ip_prefix: Union[ipaddress.IPv6Network, ipaddress.IPv4Network],
    db: InfrahubDatabase,
    branch: Optional[Union[Branch, str]] = None,
    at=None,
) -> Iterable[IPAddressData]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixIPAddressFetch.init(db=db, branch=branch, ip_prefix=ip_prefix, at=at)
    await query.execute(db=db)
    return query.get_addresses()


# FIXME: maybe belongs somewhere else or need rewrite, don't actualy use queries
async def get_utilization(
    ip_prefix: Node, db: InfrahubDatabase, branch: Optional[Union[Branch, str]] = None, at=None
) -> float:
    nodes = await ip_prefix.children.get_peers(db=db)

    prefix_space = ip_prefix.prefix.num_addresses
    free_ip_space = ip_prefix.prefix.num_addresses
    if nodes:
        # There are subnets, count space allocated by those
        for node in nodes.values():
            free_ip_space -= node.prefix.num_addresses
    else:
        # This is a subnet of hosts, count IP addresses
        free_ip_space -= len(ip_prefix.ip_addresses)

        # Non-RFC3021 subnet
        if ip_prefix.prefix.version == 4 and ip_prefix.prefix.prefixlen < 31:
            prefix_space -= 2
            free_ip_space -= 2

    # Return used percentage
    return 100 - 100 * free_ip_space / prefix_space


async def get_ip_prefix_for_ip_address(
    ip_address: Union[ipaddress.IPv6Interface, ipaddress.IPv4Interface],
    db: InfrahubDatabase,
    branch: Optional[Union[Branch, str]] = None,
    at=None,
) -> IPAddressData:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPAddressIPPrefixFetch.init(db=db, branch=branch, ip_address=ip_address, at=at)
    await query.execute(db=db)
    return query.get_prefix_for_address()
