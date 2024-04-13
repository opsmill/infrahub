from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, List, Optional, Union

from infrahub.core.constants import InfrahubKind
from infrahub.core.registry import registry

from . import Query

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


class IPPrefixUtilization(Query):
    name: str = "ipprefix_utilization"

    def __init__(self, ip_prefix: Node, *args, **kwargs):
        self.ip_prefix = ip_prefix
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["pfx_uuid"] = self.ip_prefix.id

        if self.ip_prefix.member_type.value == "prefix":
            self.params["rel_identifier"] = "parent__child"
            query = """
            MATCH (rl:Relationship { name: $rel_identifier })
            CALL {
                WITH rl
                MATCH path = (peer_node:%(label)s)-[r:IS_RELATED]-(rl)-[:IS_RELATED]-(remote_peer:%(label)s)-[:HAS_ATTRIBUTE]-(:Attribute {name: "prefix"})-[:HAS_VALUE]-(av:AttributeIPNetwork)
                WHERE peer_node.uuid = $pfx_uuid AND %(branch_filter)s
                RETURN peer_node as peer, r, remote_peer as remote, av as remote_value
                ORDER BY r.branch_level DESC, r.from DESC
                LIMIT 1
            }
            WITH peer as peer_node, r, rl, remote as remote_peer, remote_value as av
            WHERE r.status = "active"
            """ % {"label": InfrahubKind.IPPREFIX, "branch_filter": branch_filter}  # noqa: E501

            self.return_labels = ["peer_node.uuid", "COUNT(peer_node.uuid) as nbr_peers", "rl", "remote_peer", "av"]
        else:
            self.params["rel_identifier"] = "ip_prefix__ip_address"
            query = """
            MATCH (rl:Relationship { name: $rel_identifier })
            CALL {
                WITH rl
                MATCH path = (peer_node:%(label)s)-[r:IS_RELATED]->(rl)
                WHERE peer_node.uuid = $pfx_uuid AND %(branch_filter)s
                RETURN peer_node as peer, r as r1
                ORDER BY r.branch_level DESC, r.from DESC
                LIMIT 1
            }
            WITH peer as peer_node, r1 as r
            WHERE r.status = "active"
            """ % {"label": InfrahubKind.IPPREFIX, "branch_filter": branch_filter}

            self.return_labels = ["peer_node.uuid", "COUNT(peer_node.uuid) as nbr_peers"]

        self.add_to_query(query)

    async def get_percentage(self):
        prefix_space = self.ip_prefix.prefix.num_addresses
        free_ip_space = self.ip_prefix.prefix.num_addresses

        if self.ip_prefix.member_type.value == "prefix":
            for result in self.get_results():
                net = ipaddress.ip_network(result.get("av").get("value"))
                # Exclude less specific (parent)
                if net.prefixlen <= self.ip_prefix.prefix.prefixlen:
                    continue
                free_ip_space -= net.num_addresses
        else:
            result = self.get_result()
            if result:
                free_ip_space -= result.get("nbr_peers")

                # Non-RFC3021 subnet
                if (
                    self.ip_prefix.prefix.version == 4
                    and self.ip_prefix.prefix.prefixlen < 31
                    and not self.ip_prefix.is_pool.value
                ):
                    prefix_space -= 2
                    free_ip_space -= 2

        # Return used percentage
        return 100 - 100 * free_ip_space / prefix_space


async def get_utilization(
    ip_prefix: Node, db: InfrahubDatabase, branch: Optional[Union[Branch, str]] = None, at=None
) -> float:
    query = await IPPrefixUtilization.init(db, branch=branch, at=at, ip_prefix=ip_prefix)
    await query.execute(db=db)

    return await query.get_percentage()
