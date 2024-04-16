from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, List, Optional, Union

from infrahub.core.constants import InfrahubKind
from infrahub.core.registry import registry
from infrahub.core.utils import convert_ip_to_binary_str

from . import Query

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.timestamp import Timestamp
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

    def __init__(
        self,
        obj: Union[ipaddress.IPv6Network, ipaddress.IPv4Network],
        namespace: Optional[Union[Node, str]] = None,
        *args,
        **kwargs,
    ):
        self.obj = obj

        if namespace and isinstance(namespace, str):
            self.namespace_id = namespace
        elif namespace and hasattr(namespace, "id"):
            self.namespace_id = namespace.id
        else:
            self.namespace_id = registry.default_ipnamespace

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.params["ns_id"] = self.namespace_id

        prefix_bin = convert_ip_to_binary_str(self.obj)[: self.obj.prefixlen]
        self.params["prefix_binary"] = prefix_bin
        self.params["maxprefixlen"] = self.obj.prefixlen
        self.params["ip_version"] = self.obj.version

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        # ruff: noqa: E501
        query = """
        // First match on IPNAMESPACE
        MATCH (ns:%(ns_label)s)
        WHERE ns.uuid = $ns_id
        CALL {
            WITH ns
            MATCH (ns)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN ns as ns1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH ns, r1 as r
        WHERE r.status = "active"
        WITH ns
        // MATCH all prefixes that are IN SCOPE
        MATCH path2 = (ns)-[:IS_RELATED]-(ns_rel:Relationship)-[:IS_RELATED]-(pfx:%(node_label)s)-[:HAS_ATTRIBUTE]-(an:Attribute {name: "prefix"})-[:HAS_VALUE]-(av:AttributeIPNetwork)
        WHERE ns_rel.name = "ip_namespace__ip_prefix"
            AND av.binary_address STARTS WITH $prefix_binary
            AND av.prefixlen > $maxprefixlen
            AND av.version = $ip_version
            AND all(r IN relationships(path2) WHERE (%(branch_filter)s))
        // TODO Need to check for delete nodes
        WITH
            collect([pfx, av]) as all_prefixes_and_value,
            collect(pfx) as all_prefixes
        // ---
        // FIND ALL CHILDREN OF THESE PREFIXES
        // ---
        CALL {
            WITH all_prefixes
            UNWIND all_prefixes as prefix
            OPTIONAL MATCH (prefix)<-[:IS_RELATED]-(ch_rel:Relationship)<-[:IS_RELATED]-(children:BuiltinIPPrefix)
            WHERE ch_rel.name = "parent__child"
            RETURN children
        }
        WITH collect( distinct children ) AS all_children, all_prefixes_and_value
        UNWIND all_prefixes_and_value as prefixes_to_check
        WITH prefixes_to_check, all_children
        WHERE not prefixes_to_check[0] in all_children
        """ % {
            "ns_label": InfrahubKind.IPNAMESPACE,
            "node_label": InfrahubKind.IPPREFIX,
            "branch_filter": branch_filter,
        }

        self.add_to_query(query)
        self.return_labels = ["prefixes_to_check[0] as pfx", "prefixes_to_check[1] as av"]
        self.order_by = ["av.binary_address"]

    def get_subnets(self):
        """Return a list of all subnets fitting in the prefix."""
        subnets: List[IPPrefixData] = []

        for result in self.get_results():
            subnet = IPPrefixData(
                id=result.get("pfx").get("uuid"), prefix=ipaddress.ip_network(result.get("av").get("value"))
            )
            subnets.append(subnet)

        return subnets


class IPPrefixContainerFetch(Query):
    name: str = "ipprefix_container_fetch"

    def __init__(
        self,
        obj: Union[ipaddress.IPv6Network, ipaddress.IPv4Network, ipaddress.IPv4Interface, ipaddress.IPv6Interface],
        namespace: Optional[Union[Node, str]] = None,
        *args,
        **kwargs,
    ):
        self.obj = obj

        if namespace and isinstance(namespace, str):
            self.namespace_id = namespace
        elif namespace and hasattr(namespace, "id"):
            self.namespace_id = namespace.id
        else:
            self.namespace_id = registry.default_ipnamespace

        if isinstance(obj, (ipaddress.IPv6Network, ipaddress.IPv4Network)):
            self.prefixlen = obj.prefixlen
            self.minprefixlen = obj.prefixlen
        elif isinstance(obj, (ipaddress.IPv4Interface, ipaddress.IPv6Interface)):
            self.prefixlen = obj.network.prefixlen
            self.minprefixlen = self.prefixlen + 1

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.params["ns_id"] = self.namespace_id
        prefix_bin = convert_ip_to_binary_str(self.obj)[: self.prefixlen]

        self.params["minprefixlen"] = self.minprefixlen
        self.params["ip_version"] = self.obj.version

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        possible_prefixes = set()
        for idx in range(1, self.prefixlen):
            tmp_prefix = prefix_bin[: self.prefixlen - idx]
            padding = "0" * (self.obj.max_prefixlen - len(tmp_prefix))
            possible_prefixes.add(f"{tmp_prefix}{padding}")

        self.params["possible_prefixes"] = list(possible_prefixes)

        # ruff: noqa: E501
        query = """
        // First match on IPNAMESPACE
        MATCH (ns:%(ns_label)s)
        WHERE ns.uuid = $ns_id
        CALL {
            WITH ns
            MATCH (ns)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN ns as ns1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH ns, r1 as r
        WHERE r.status = "active"
        WITH ns
        // MATCH all prefixes that are IN SCOPE
        MATCH path2 = (ns)-[:IS_RELATED]-(ns_rel:Relationship)-[:IS_RELATED]-(pfx:%(node_label)s)-[:HAS_ATTRIBUTE]-(an:Attribute {name: "prefix"})-[:HAS_VALUE]-(av:AttributeIPNetwork)
        WHERE ns_rel.name = "ip_namespace__ip_prefix"
            AND av.binary_address IN $possible_prefixes
            AND av.prefixlen < $minprefixlen
            AND av.version = $ip_version
            AND all(r IN relationships(path2) WHERE (%(branch_filter)s))
        """ % {
            "ns_label": InfrahubKind.IPNAMESPACE,
            "node_label": InfrahubKind.IPPREFIX,
            "branch_filter": branch_filter,
        }

        self.add_to_query(query)
        self.return_labels = ["pfx", "av"]
        self.order_by = ["av.prefixlen"]

    def get_container(self) -> Optional[IPPrefixData]:
        """Return the more specific prefix that contains this one."""
        candidates: List[IPPrefixData] = []

        if not self.num_of_results:
            return None

        for result in self.get_results():
            candidate = IPPrefixData(
                id=result.get("pfx").get("uuid"), prefix=ipaddress.ip_network(result.get("av").get("value"))
            )
            candidates.append(candidate)
        return candidates[-1]


class IPPrefixIPAddressFetch(Query):
    name: str = "ipprefix_ipaddress_fetch"

    def __init__(
        self,
        obj: Union[ipaddress.IPv6Network, ipaddress.IPv4Network],
        namespace: Optional[Union[Node, str]] = None,
        *args,
        **kwargs,
    ):
        self.obj = obj

        if namespace and isinstance(namespace, str):
            self.namespace_id = namespace
        elif namespace and hasattr(namespace, "id"):
            self.namespace_id = namespace.id
        else:
            self.namespace_id = registry.default_ipnamespace

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.params["ns_id"] = self.namespace_id

        prefix_bin = convert_ip_to_binary_str(self.obj)[: self.obj.prefixlen]
        self.params["prefix_binary"] = prefix_bin
        self.params["maxprefixlen"] = self.obj.prefixlen
        self.params["ip_version"] = self.obj.version

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        # ruff: noqa: E501
        query = """
        // First match on IPNAMESPACE
        MATCH (ns:%(ns_label)s)
        WHERE ns.uuid = $ns_id
        CALL {
            WITH ns
            MATCH (ns)-[r:IS_PART_OF]-(root:Root)
            WHERE %(branch_filter)s
            RETURN ns as ns1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH ns, r1 as r
        WHERE r.status = "active"
        WITH ns
        // MATCH all IPAddress that are IN SCOPE
        MATCH path2 = (ns)-[:IS_RELATED]-(ns_rel:Relationship)-[:IS_RELATED]-(addr:%(node_label)s)-[:HAS_ATTRIBUTE]-(an:Attribute {name: "address"})-[:HAS_VALUE]-(av:AttributeIPHost)
        WHERE ns_rel.name = "ip_namespace__ip_address"
            AND av.binary_address STARTS WITH $prefix_binary
            AND av.prefixlen >= $maxprefixlen
            AND av.version = $ip_version
            AND all(r IN relationships(path2) WHERE (%(branch_filter)s))
        """ % {
            "ns_label": InfrahubKind.IPNAMESPACE,
            "node_label": InfrahubKind.IPADDRESS,
            "branch_filter": branch_filter,
        }

        self.add_to_query(query)
        self.return_labels = ["addr", "av"]
        self.order_by = ["av.binary_address"]

    def get_addresses(self):
        """Return a list of all addresses fitting in the prefix."""
        addresses: List[IPAddressData] = []

        for result in self.get_results():
            address = IPAddressData(
                id=result.get("addr").get("uuid"), address=ipaddress.ip_interface(result.get("av").get("value"))
            )
            addresses.append(address)

        return addresses


async def get_container(
    db: InfrahubDatabase,
    ip_prefix: Union[ipaddress.IPv6Network, ipaddress.IPv4Network],
    namespace: Optional[Union[Node, str]] = None,
    branch: Optional[Union[Branch, str]] = None,
    at: Optional[Union[Timestamp, str]] = None,
) -> Optional[IPPrefixData]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixContainerFetch.init(db=db, branch=branch, obj=ip_prefix, namespace=namespace, at=at)
    await query.execute(db=db)
    return query.get_container()


async def get_subnets(
    db: InfrahubDatabase,
    ip_prefix: Union[ipaddress.IPv6Network, ipaddress.IPv4Network],
    namespace: Optional[Union[Node, str]] = None,
    branch: Optional[Union[Branch, str]] = None,
    at: Optional[Union[Timestamp, str]] = None,
) -> Iterable[IPPrefixData]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixSubnetFetch.init(db=db, branch=branch, obj=ip_prefix, namespace=namespace, at=at)
    await query.execute(db=db)
    return query.get_subnets()


async def get_ip_addresses(
    db: InfrahubDatabase,
    ip_prefix: Union[ipaddress.IPv6Network, ipaddress.IPv4Network],
    namespace: Optional[Union[Node, str]] = None,
    branch: Optional[Union[Branch, str]] = None,
    at=None,
) -> Iterable[IPAddressData]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixIPAddressFetch.init(db=db, branch=branch, obj=ip_prefix, namespace=namespace, at=at)
    await query.execute(db=db)
    return query.get_addresses()


async def get_ip_prefix_for_ip_address(
    db: InfrahubDatabase,
    ip_address: Union[ipaddress.IPv6Interface, ipaddress.IPv4Interface],
    namespace: Optional[str] = None,
    branch: Optional[Union[Branch, str]] = None,
    at: Optional[Union[Timestamp, str]] = None,
) -> Optional[IPPrefixData]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixContainerFetch.init(db=db, branch=branch, obj=ip_address, namespace=namespace, at=at)
    await query.execute(db=db)
    return query.get_container()


class IPPrefixUtilizationPrefix(Query):
    name: str = "ipprefix_utilization_prefix"

    def __init__(self, ip_prefix: Node, *args, **kwargs):
        self.ip_prefix = ip_prefix
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["id"] = self.ip_prefix.id

        query = """
        MATCH path = (pfx:Node)<-[:IS_RELATED]-(rl:Relationship)<-[:IS_RELATED]-(children:%(label)s)
        WHERE pfx.uuid = $id
          AND all(r IN relationships(path) WHERE (%(branch_filter)s))
          AND rl.name = "parent__child"
        CALL {
            WITH pfx, children
            MATCH path = (pfx)<-[r1:IS_RELATED]-(rl:Relationship)<-[r2:IS_RELATED]-(children:%(label)s)
            WHERE all(r IN relationships(path) WHERE (%(branch_filter)s))
                AND rl.name = "parent__child"
            RETURN r1 as r11, r2 as r21
            ORDER BY r1.branch_level DESC, r1.from DESC, r2.branch_level DESC, r2.from DESC
            LIMIT 1
        }
        WITH pfx, children, r11, r21
        WHERE r11.status = "active" AND r21.status = "active"
        CALL {
            WITH children
            MATCH path = (children)-[r1:HAS_ATTRIBUTE]-(:Attribute {name: "prefix"})-[r2:HAS_VALUE]-(av:AttributeIPNetwork)
            WHERE all(r IN relationships(path) WHERE (%(branch_filter)s))
            RETURN r1 as r12, r2 as r22, av
            ORDER BY r1.branch_level DESC, r1.from DESC, r2.branch_level DESC, r2.from DESC
            LIMIT 1
        }
        WITH pfx, children, r12, r22, av
        WHERE r12.status = "active" AND r22.status = "active"
        """ % {"label": InfrahubKind.IPPREFIX, "branch_filter": branch_filter}  # noqa: E501

        self.return_labels = ["av.prefixlen as prefixlen"]

        self.add_to_query(query)

    def get_percentage(self):
        prefix_space = self.ip_prefix.prefix.num_addresses
        max_prefixlen = self.ip_prefix.prefix.obj.max_prefixlen
        used_space = 0
        for result in self.get_results():
            used_space += 2 ** (max_prefixlen - int(result.get("prefixlen")))

        return (used_space / prefix_space) * 100


class IPPrefixUtilizationAddress(Query):
    name: str = "ipprefix_utilization_address"

    def __init__(self, ip_prefix: Node, *args, **kwargs):
        self.ip_prefix = ip_prefix
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["id"] = self.ip_prefix.id

        query = """
        MATCH path = (pfx:Node)-[:IS_RELATED]->(rl:Relationship)<-[:IS_RELATED]-(children:%(label)s)
        WHERE pfx.uuid = $id
          AND all(r IN relationships(path) WHERE (%(branch_filter)s))
          AND rl.name = "ip_prefix__ip_address"
        CALL {
            WITH pfx, children
            MATCH path = (pfx)-[r1:IS_RELATED]->(rl:Relationship)<-[r2:IS_RELATED]-(children:%(label)s)
            WHERE all(r IN relationships(path) WHERE (%(branch_filter)s))
                AND rl.name = "ip_prefix__ip_address"
            RETURN r1, r2
            ORDER BY r1.branch_level DESC, r1.from DESC, r2.branch_level DESC, r2.from DESC
            LIMIT 1
        }
        WITH pfx, children, r1, r2
        WHERE r1.status = "active" AND r2.status = "active"
        """ % {"label": InfrahubKind.IPADDRESS, "branch_filter": branch_filter}  # noqa: E501

        self.return_labels = ["count(children) as nbr_children"]

        self.add_to_query(query)

    def get_percentage(self):
        prefix_space = self.ip_prefix.prefix.num_addresses

        # Non-RFC3021 subnet
        if (
            self.ip_prefix.prefix.version == 4
            and self.ip_prefix.prefix.prefixlen < 31
            and not self.ip_prefix.is_pool.value
        ):
            prefix_space -= 2

        return (self.get_result().get("nbr_children") / prefix_space) * 100


async def get_utilization(
    ip_prefix: Node,
    db: InfrahubDatabase,
    branch: Optional[Branch] = None,
    at: Optional[Union[Timestamp, str]] = None,
) -> float:
    if ip_prefix.member_type.value == "address":
        query = await IPPrefixUtilizationAddress.init(db, branch=branch, at=at, ip_prefix=ip_prefix)
    else:
        query = await IPPrefixUtilizationPrefix.init(db, branch=branch, at=at, ip_prefix=ip_prefix)

    await query.execute(db=db)
    return query.get_percentage()
