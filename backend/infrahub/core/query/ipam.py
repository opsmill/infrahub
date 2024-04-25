from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, List, Optional, Union

from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.constants import AllIPTypes, IPAddressType, IPNetworkType
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
    prefix: IPNetworkType


@dataclass
class IPAddressData:
    id: UUID
    address: IPAddressType


def _get_namespace_id(
    namespace: Optional[Union[Node, str]] = None,
) -> str:
    if namespace and isinstance(namespace, str):
        return namespace
    if namespace and hasattr(namespace, "id"):
        return namespace.id
    return registry.default_ipnamespace


class IPPrefixSubnetFetch(Query):
    name: str = "ipprefix_subnet_fetch"

    def __init__(
        self,
        obj: IPNetworkType,
        namespace: Optional[Union[Node, str]] = None,
        *args,
        **kwargs,
    ):
        self.obj = obj
        self.namespace_id = _get_namespace_id(namespace)

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
        self.namespace_id = _get_namespace_id(namespace)

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
        obj: IPNetworkType,
        namespace: Optional[Union[Node, str]] = None,
        *args,
        **kwargs,
    ):
        self.obj = obj
        self.namespace_id = _get_namespace_id(namespace)

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
    ip_prefix: IPNetworkType,
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
    ip_prefix: IPNetworkType,
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
    ip_prefix: IPNetworkType,
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
    ip_address: IPAddressType,
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


class IPPrefixReconcileQuery(Query):
    name: str = "ip_prefix_reconcile"

    def __init__(
        self,
        ip_value: AllIPTypes,
        namespace: Optional[Union[Node, str]] = None,
        node_uuid: Optional[str] = None,
        *args,
        **kwargs,
    ):
        self.ip_value = ip_value
        self.ip_uuid = node_uuid
        self.namespace_id = _get_namespace_id(namespace)
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params["ip_prefix_kind"] = InfrahubKind.IPPREFIX
        self.params["ip_address_kind"] = InfrahubKind.IPADDRESS
        self.params["ip_prefix_attribute_kind"] = "AttributeIPNetwork"
        self.params["ip_address_attribute_kind"] = "AttributeIPHost"
        self.params["namespace_kind"] = InfrahubKind.IPNAMESPACE
        self.params["namespace_id"] = self.namespace_id
        prefix_bin = convert_ip_to_binary_str(self.ip_value)
        self.params["prefix_binary"] = prefix_bin
        if isinstance(self.ip_value, IPAddressType):
            prefixlen = self.ip_value.max_prefixlen
        else:
            prefixlen = self.ip_value.prefixlen
        self.params["prefixlen"] = prefixlen
        self.params["ip_version"] = self.ip_value.version
        possible_prefixes = set()
        for idx in range(1, prefixlen):
            tmp_prefix = prefix_bin[: prefixlen - idx]
            padding = "0" * (self.ip_value.max_prefixlen - len(tmp_prefix))
            possible_prefixes.add(f"{tmp_prefix}{padding}")
        self.params["possible_prefixes"] = list(possible_prefixes)

        namespace_query = """
        // Get IP Namespace
        MATCH (ip_namespace:%(namespace_kind)s)-[r:IS_PART_OF]->(root:Root)
        WHERE ip_namespace.uuid = $namespace_id
        AND %(branch_filter)s
        """ % {"branch_filter": branch_filter, "namespace_kind": self.params["namespace_kind"]}
        self.add_to_query(namespace_query)

        if self.ip_uuid:
            self.params["node_uuid"] = self.ip_uuid
            get_node_by_id_query = """
            // Get IP Prefix node by UUID
            MATCH (ip_node {uuid: $node_uuid})
            """
            self.add_to_query(get_node_by_id_query)

        else:
            get_node_by_prefix_query = """
            // Get IP Prefix node by prefix value
            OPTIONAL MATCH ip_node_path = (:Root)<-[:IS_PART_OF]-(ip_node:Node)-[:HAS_ATTRIBUTE]->(a:Attribute)-[:HAS_VALUE]->(aipn), (ip_namespace)-[:IS_RELATED]-(nsr:Relationship)-[:IS_RELATED]-(ip_node)
            WHERE any(label IN LABELS(ip_node) WHERE label IN [$ip_prefix_kind, $ip_address_kind])
            AND nsr.name IN ["ip_namespace__ip_prefix", "ip_namespace__ip_address"]
            AND any(label IN LABELS(aipn) WHERE label IN [$ip_prefix_attribute_kind, $ip_address_attribute_kind])
            AND aipn.binary_address = $prefix_binary
            AND aipn.prefixlen = $prefixlen
            AND aipn.version = $ip_version
            AND all(r IN relationships(ip_node_path) WHERE (%(branch_filter)s) and r.status = "active")
            """ % {
                "branch_filter": branch_filter,
            }
            self.add_to_query(get_node_by_prefix_query)

        get_current_parent_query = """
        // Get prefix node's current parent, if it exists
        OPTIONAL MATCH parent_prefix_path = (ip_node)-[:IS_RELATED]->(:Relationship {name: "parent__child"})-[:IS_RELATED]->(current_parent:%(ip_prefix_kind)s)
        WHERE all(r IN relationships(parent_prefix_path) WHERE (%(branch_filter)s) and r.status = "active")
        """ % {
            "branch_filter": branch_filter,
            "ip_prefix_kind": self.params["ip_prefix_kind"],
        }
        self.add_to_query(get_current_parent_query)

        get_current_children_query = """
        // Get prefix node's current prefix children, if any exist
        OPTIONAL MATCH child_prefix_path = (ip_node)<-[:IS_RELATED]-(:Relationship {name: "parent__child"})<-[:IS_RELATED]-(current_prefix_child:%(ip_prefix_kind)s)
        WHERE all(r IN relationships(child_prefix_path) WHERE (%(branch_filter)s) and r.status = "active")
        WITH ip_namespace, ip_node, current_parent, collect(current_prefix_child) AS current_prefix_children
        // Get prefix node's current address children, if any exist
        OPTIONAL MATCH child_address_path = (ip_node)-[:IS_RELATED]-(:Relationship {name: "ip_prefix__ip_address"})-[:IS_RELATED]-(current_address_child:%(ip_address_kind)s)
        WHERE all(r IN relationships(child_address_path) WHERE (%(branch_filter)s) and r.status = "active")
        WITH ip_namespace, ip_node, current_parent, current_prefix_children, collect(current_address_child) AS current_address_children
        WITH ip_namespace, ip_node, current_parent, current_prefix_children + current_address_children AS current_children
        """ % {
            "branch_filter": branch_filter,
            "ip_prefix_kind": self.params["ip_prefix_kind"],
            "ip_address_kind": self.params["ip_address_kind"],
        }
        self.add_to_query(get_current_children_query)

        get_new_parent_query = """
        // Identify the correct parent, if any, for the prefix node
        CALL {
            WITH ip_namespace
            OPTIONAL MATCH parent_path = (ip_namespace)-[pr1:IS_RELATED]-(ns_rel:Relationship)-[pr2:IS_RELATED]-(maybe_new_parent:%(ip_prefix_kind)s)-[har:HAS_ATTRIBUTE]->(:Attribute {name: "prefix"})-[hvr:HAS_VALUE]->(av:%(ip_prefix_attribute_kind)s)
            WHERE ns_rel.name = "ip_namespace__ip_prefix"
            AND all(r IN relationships(parent_path) WHERE (%(branch_filter)s))
            AND pr1.status = "active"
            AND pr2.status = "active"
            AND av.binary_address IN $possible_prefixes
            AND av.prefixlen < $prefixlen
            AND av.version = $ip_version
            WITH
                maybe_new_parent,
                har,
                hvr,
                av.prefixlen as prefixlen,
                (har.status = "active" AND hvr.status = "active") AS is_active,
                har.branch_level + hvr.branch_level AS branch_level
            RETURN maybe_new_parent, prefixlen AS mnp_prefixlen, is_active AS mnp_is_active
            ORDER BY branch_level DESC, har.from DESC, hvr.from DESC
            LIMIT 1
        }
        WITH ip_namespace, ip_node, current_parent, current_children, maybe_new_parent, mnp_is_active, mnp_prefixlen
        ORDER BY ip_node.uuid, mnp_is_active DESC, mnp_prefixlen DESC
        WITH ip_namespace, ip_node, current_parent, current_children, head(collect(maybe_new_parent)) as new_parent
        """ % {
            "branch_filter": branch_filter,
            "ip_prefix_kind": self.params["ip_prefix_kind"],
            "ip_prefix_attribute_kind": self.params["ip_prefix_attribute_kind"],
        }
        self.add_to_query(get_new_parent_query)

        get_new_children_query = """
        // Identify the correct children, if any, for the prefix node
        CALL {
            // Get ALL possible children for the prefix node
            WITH ip_namespace, ip_node
            OPTIONAL MATCH child_path = (ip_namespace)-[:IS_RELATED]-(ns_rel:Relationship)-[:IS_RELATED]-(maybe_new_child)-[har:HAS_ATTRIBUTE]->(a:Attribute)-[hvr:HAS_VALUE]->(av:AttributeValue)
            WHERE (ip_node IS NULL OR maybe_new_child.uuid <> ip_node.uuid)
            AND ns_rel.name IN ["ip_namespace__ip_prefix", "ip_namespace__ip_address"]
            AND a.name in ["prefix", "address"]
            AND any(label IN LABELS(maybe_new_child) WHERE label IN [$ip_prefix_kind, $ip_address_kind])
            AND any(label IN LABELS(av) WHERE label IN [$ip_prefix_attribute_kind, $ip_address_attribute_kind])
            AND (
                ($ip_prefix_kind IN LABELS(maybe_new_child) AND av.prefixlen > $prefixlen)
                OR ($ip_address_kind IN LABELS(maybe_new_child) AND av.prefixlen >= $prefixlen)
            )
            AND av.version = $ip_version
            AND av.binary_address STARTS WITH SUBSTRING($prefix_binary, 0, $prefixlen)
            AND all(r IN relationships(child_path) WHERE (%(branch_filter)s) AND r.status = "active")
            WITH
                maybe_new_child,
                av AS mnc_attribute,
                har,
                hvr,
                (har.status = "active" AND hvr.status = "active") AS is_active,
                har.branch_level + hvr.branch_level AS branch_level
            ORDER BY maybe_new_child.uuid, branch_level DESC, har.from DESC, hvr.from DESC
            WITH maybe_new_child, head(collect([mnc_attribute, is_active])) AS latest_mnc_details
            RETURN maybe_new_child, latest_mnc_details[0] AS latest_mnc_attribute, latest_mnc_details[1] AS mnc_is_active
        }
        WITH ip_namespace, ip_node, current_parent, current_children, new_parent, maybe_new_child, latest_mnc_attribute, mnc_is_active
        WHERE mnc_is_active = TRUE OR mnc_is_active IS NULL
        WITH ip_namespace, ip_node, current_parent, current_children, new_parent, collect([maybe_new_child, latest_mnc_attribute]) AS maybe_children_ips
        WITH ip_namespace, ip_node, current_parent, current_children, new_parent, maybe_children_ips, range(0, size(maybe_children_ips) - 1) AS child_indices
        UNWIND child_indices as ind
        CALL {
            // Filter all possible children to remove those that have a more-specific parent
            // among the list of all possible children
            WITH ind, maybe_children_ips
            WITH ind, maybe_children_ips AS ips
            RETURN REDUCE(
                has_more_specific_parent = FALSE, potential_parent IN ips |
                CASE
                    WHEN has_more_specific_parent THEN has_more_specific_parent  // keep it True once set
                    WHEN potential_parent IS NULL OR ips[ind][0] IS NULL THEN has_more_specific_parent
                    WHEN potential_parent[0] = ips[ind][0] THEN has_more_specific_parent  // skip comparison to self
                    WHEN $ip_address_kind in LABELS(potential_parent[0]) THEN has_more_specific_parent  // address cannot be a parent
                    WHEN $ip_prefix_attribute_kind IN LABELS(ips[ind][1]) AND (potential_parent[1]).prefixlen >= (ips[ind][1]).prefixlen THEN has_more_specific_parent  // prefix with same or greater prefixlen for prefix cannot be parent
                    WHEN $ip_address_attribute_kind IN LABELS(ips[ind][1]) AND (potential_parent[1]).prefixlen > (ips[ind][1]).prefixlen THEN has_more_specific_parent  // prefix with greater prefixlen for address cannot be parent
                    WHEN (ips[ind][1]).binary_address STARTS WITH SUBSTRING((potential_parent[1]).binary_address, 0, (potential_parent[1]).prefixlen) THEN TRUE  // we found a parent
                    ELSE has_more_specific_parent
                END
            ) as has_parent_among_maybe_children
        }
        WITH ip_namespace, ip_node, current_parent, current_children, new_parent, maybe_children_ips[ind][0] AS new_child, has_parent_among_maybe_children
        WHERE has_parent_among_maybe_children = FALSE
        WITH
            ip_namespace,
            ip_node,
            current_parent,
            current_children,
            new_parent,
            collect(new_child) as new_children
        """ % {"branch_filter": branch_filter}
        self.add_to_query(get_new_children_query)
        self.return_labels = ["ip_node", "current_parent", "current_children", "new_parent", "new_children"]

    def _get_uuid_from_query(self, node_name: str) -> Optional[str]:
        results = list(self.get_results())
        if not results:
            return None
        result = results[0]
        node = result.get(node_name)
        if not node:
            return None
        node_uuid = node.get("uuid")
        if node_uuid:
            return str(node_uuid)
        return None

    def _get_uuids_from_query_list(self, alias_name: str) -> list[str]:
        results = list(self.get_results())
        if not results:
            return []
        result = results[0]
        element_uuids = []
        for element in result.get(alias_name):
            if not element:
                continue
            element_uuid = element.get("uuid")
            if element_uuid:
                element_uuids.append(str(element_uuid))
        return element_uuids

    def get_ip_node_uuid(self) -> Optional[str]:
        return self._get_uuid_from_query("ip_node")

    def get_current_parent_uuid(self) -> Optional[str]:
        return self._get_uuid_from_query("current_parent")

    def get_calculated_parent_uuid(self) -> Optional[str]:
        return self._get_uuid_from_query("new_parent")

    def get_current_children_uuids(self) -> list[str]:
        return self._get_uuids_from_query_list("current_children")

    def get_calculated_children_uuids(self) -> list[str]:
        return self._get_uuids_from_query_list("new_children")
