from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.constants import AllIPTypes, IPAddressType, IPNetworkType
from infrahub.core.query import QueryType
from infrahub.core.registry import registry
from infrahub.core.utils import convert_ip_to_binary_str

from . import Query

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


PREFIX_ATTRIBUTE_LABEL = "AttributeIPNetwork"
ADDRESS_ATTRIBUTE_LABEL = "AttributeIPHost"


@dataclass
class IPPrefixData:
    id: UUID
    prefix: IPNetworkType


@dataclass
class IPAddressData:
    id: UUID
    address: IPAddressType


def _get_namespace_id(
    namespace: Node | str | None = None,
) -> str:
    if namespace and isinstance(namespace, str):
        return namespace
    if namespace and hasattr(namespace, "id"):
        return namespace.id
    return registry.default_ipnamespace


class IPPrefixSubnetFetch(Query):
    name = "ipprefix_subnet_fetch"
    type = QueryType.READ

    def __init__(
        self,
        obj: IPNetworkType,
        namespace: Node | str | None = None,
        **kwargs,
    ):
        self.obj = obj
        self.namespace_id = _get_namespace_id(namespace)

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["ns_id"] = self.namespace_id

        prefix_bin = convert_ip_to_binary_str(self.obj)[: self.obj.prefixlen]
        self.params["prefix_binary"] = prefix_bin
        self.params["maxprefixlen"] = self.obj.prefixlen
        self.params["ip_version"] = self.obj.version

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        # ruff: noqa: E501
        query = """
        // First match on IPNAMESPACE
        MATCH (ns:%(ns_label)s)
        WHERE ns.uuid = $ns_id
        CALL (ns) {
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
            AND all(r IN relationships(path2) WHERE (%(branch_filter)s) and r.status = "active")
        WITH
            collect([pfx, av]) as all_prefixes_and_value,
            collect(pfx) as all_prefixes
        // ---
        // FIND ALL CHILDREN OF THESE PREFIXES
        // ---
        CALL (all_prefixes) {
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

    def get_subnets(self) -> list[IPPrefixData]:
        """Return a list of all subnets fitting in the prefix."""
        subnets: list[IPPrefixData] = []

        for result in self.get_results():
            subnet = IPPrefixData(
                id=result.get("pfx").get("uuid"), prefix=ipaddress.ip_network(result.get("av").get("value"))
            )
            subnets.append(subnet)

        return subnets


class IPPrefixIPAddressFetch(Query):
    name = "ipprefix_ipaddress_fetch"
    type = QueryType.READ

    def __init__(
        self,
        obj: IPNetworkType,
        namespace: Node | str | None = None,
        **kwargs,
    ):
        self.obj = obj
        self.namespace_id = _get_namespace_id(namespace)

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["ns_id"] = self.namespace_id

        prefix_bin = convert_ip_to_binary_str(self.obj)[: self.obj.prefixlen]
        self.params["prefix_binary"] = prefix_bin
        self.params["maxprefixlen"] = self.obj.prefixlen
        self.params["ip_version"] = self.obj.version

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        # ruff: noqa: E501
        query = """
        // First match on IPNAMESPACE
        MATCH (ns:%(ns_label)s)
        WHERE ns.uuid = $ns_id
        CALL (ns) {
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
            AND all(r IN relationships(path2) WHERE (%(branch_filter)s) and r.status = "active")
        """ % {
            "ns_label": InfrahubKind.IPNAMESPACE,
            "node_label": InfrahubKind.IPADDRESS,
            "branch_filter": branch_filter,
        }

        self.add_to_query(query)
        self.return_labels = ["addr", "av"]
        self.order_by = ["av.binary_address"]

    def get_addresses(self) -> list[IPAddressData]:
        """Return a list of all addresses fitting in the prefix."""
        addresses: list[IPAddressData] = []

        for result in self.get_results():
            address = IPAddressData(
                id=result.get("addr").get("uuid"), address=ipaddress.ip_interface(result.get("av").get("value"))
            )
            addresses.append(address)

        return addresses


async def get_subnets(
    db: InfrahubDatabase,
    ip_prefix: IPNetworkType,
    namespace: Node | str | None = None,
    branch: Branch | str | None = None,
    at: Timestamp | str | None = None,
    branch_agnostic: bool = False,
) -> Iterable[IPPrefixData]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixSubnetFetch.init(
        db=db, branch=branch, obj=ip_prefix, namespace=namespace, at=at, branch_agnostic=branch_agnostic
    )
    await query.execute(db=db)
    return query.get_subnets()


async def get_ip_addresses(
    db: InfrahubDatabase,
    ip_prefix: IPNetworkType,
    namespace: Node | str | None = None,
    branch: Branch | str | None = None,
    at: Timestamp | str | None = None,
    branch_agnostic: bool = False,
) -> Iterable[IPAddressData]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixIPAddressFetch.init(
        db=db, branch=branch, obj=ip_prefix, namespace=namespace, at=at, branch_agnostic=branch_agnostic
    )
    await query.execute(db=db)
    return query.get_addresses()


class IPPrefixUtilization(Query):
    name = "ipprefix_utilization_prefix"
    type = QueryType.READ

    def __init__(self, ip_prefixes: list[str], allocated_kinds: list[str], **kwargs):
        self.ip_prefixes = ip_prefixes
        self.allocated_kinds: list[str] = []
        self.allocated_kinds_rel: list[str] = []

        for kind in sorted(allocated_kinds):
            self.allocated_kinds.append(f'"{kind}"')
            self.allocated_kinds_rel.append(
                {InfrahubKind.IPADDRESS: '"ip_prefix__ip_address"', InfrahubKind.IPPREFIX: '"parent__child"'}[kind]
            )

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["ids"] = [p.get_id() for p in self.ip_prefixes]
        self.params["time_at"] = self.at.to_string()

        def rel_filter(rel_name: str) -> str:
            return f"{rel_name}.from <= $time_at AND ({rel_name}.to IS NULL OR {rel_name}.to >= $time_at)"

        query = f"""
        MATCH (pfx:Node)
        WHERE pfx.uuid IN $ids
        CALL (pfx) {{
            MATCH (pfx)-[r_rel1:IS_RELATED]-(rl:Relationship)<-[r_rel2:IS_RELATED]-(child:Node)
            WHERE rl.name IN [{", ".join(self.allocated_kinds_rel)}]
            AND any(l IN labels(child) WHERE l IN [{", ".join(self.allocated_kinds)}])
            AND ({rel_filter("r_rel1")})
            AND ({rel_filter("r_rel2")})
            RETURN r_rel1, rl, r_rel2, child
        }}
        WITH pfx, r_rel1, rl, r_rel2, child
        MATCH path = (
            (pfx)-[r_1:IS_RELATED]-(rl:Relationship)-[r_2:IS_RELATED]-(child:Node)
            -[r_attr:HAS_ATTRIBUTE]->(attr:Attribute)
            -[r_attr_val:HAS_VALUE]->(av:AttributeValue)
        )
        WHERE %(id_func)s(r_1) = %(id_func)s(r_rel1)
        AND %(id_func)s(r_2) = %(id_func)s(r_rel2)
        AND ({rel_filter("r_attr")})
        AND ({rel_filter("r_attr_val")})
        AND attr.name IN ["prefix", "address"]
        AND any(l in labels(av) WHERE l in ["{PREFIX_ATTRIBUTE_LABEL}", "{ADDRESS_ATTRIBUTE_LABEL}"])
        WITH
            path,
            pfx,
            child,
            av,
            reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level) AS sum_branch_level,
            all(r in relationships(path) WHERE r.status = "active") AS is_active,
            [r_attr_val.from, r_attr.from, r_2.from, r_1.from] AS from_times,
            reduce(
                b_details = [0, null], r in relationships(path) |
                CASE WHEN r.branch_level > b_details[0] THEN [r.branch_level, r.branch] ELSE b_details END
            ) as deepest_branch_details
        ORDER BY pfx.uuid, child.uuid, av.uuid, sum_branch_level DESC, from_times[3] DESC, from_times[2] DESC, from_times[1] DESC, from_times[0] DESC
        WITH
            pfx,
            child,
            av,
            deepest_branch_details[0] AS branch_level,
            deepest_branch_details[1] AS branch,
            head(collect(is_active)) AS is_latest_active
        WHERE is_latest_active = TRUE
        """ % {
            "id_func": db.get_id_function_name(),
        }
        self.return_labels = ["pfx", "child", "av", "branch_level", "branch"]
        self.add_to_query(query)


class IPPrefixReconcileQuery(Query):
    name = "ip_prefix_reconcile"
    type = QueryType.READ

    def __init__(
        self,
        ip_value: AllIPTypes,
        namespace: Node | str | None = None,
        node_uuid: str | None = None,
        **kwargs,
    ):
        self.ip_value = ip_value
        self.ip_uuid = node_uuid
        self.namespace_id = _get_namespace_id(namespace)
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params["namespace_kind"] = InfrahubKind.IPNAMESPACE
        self.params["namespace_id"] = self.namespace_id
        self.params["ip_prefix_kind"] = InfrahubKind.IPPREFIX
        self.params["ip_address_kind"] = InfrahubKind.IPADDRESS
        self.params["ip_prefix_attribute_kind"] = PREFIX_ATTRIBUTE_LABEL
        self.params["ip_address_attribute_kind"] = ADDRESS_ATTRIBUTE_LABEL

        if isinstance(self.ip_value, IPAddressType):
            is_address = True
            prefixlen = self.ip_value.network.prefixlen
        else:
            is_address = False
            prefixlen = self.ip_value.prefixlen
        self.params["is_prefix"] = not is_address
        self.params["prefixlen"] = prefixlen
        prefix_bin = convert_ip_to_binary_str(self.ip_value)
        prefix_bin_host = prefix_bin[:prefixlen]
        self.params["prefix_binary_full"] = prefix_bin
        self.params["prefix_binary_host"] = prefix_bin_host
        self.params["ip_version"] = self.ip_value.version
        # possible prefix: highest possible prefix length for a match
        possible_prefix_map: dict[str, int] = {}
        start_prefixlen = prefixlen if is_address else prefixlen - 1
        for max_prefix_len in range(start_prefixlen, -1, -1):
            tmp_prefix = prefix_bin_host[:max_prefix_len]
            possible_prefix = tmp_prefix.ljust(self.ip_value.max_prefixlen, "0")
            if possible_prefix not in possible_prefix_map:
                possible_prefix_map[possible_prefix] = max_prefix_len
        self.params["possible_prefix_and_length_list"] = []
        self.params["possible_prefix_list"] = []
        for possible_prefix, max_length in possible_prefix_map.items():
            self.params["possible_prefix_and_length_list"].append([possible_prefix, max_length])
            self.params["possible_prefix_list"].append(possible_prefix)

        namespace_query = """
        // ------------------
        // Get IP Namespace
        // ------------------
        MATCH (ip_namespace:%(namespace_kind)s {uuid: $namespace_id})-[r:IS_PART_OF]->(root:Root)
        WHERE %(branch_filter)s
        """ % {"branch_filter": branch_filter, "namespace_kind": self.params["namespace_kind"]}
        self.add_to_query(namespace_query)

        if self.ip_uuid:
            self.params["node_uuid"] = self.ip_uuid
            get_node_by_id_query = """
            // ------------------
            // Get IP Prefix node by UUID
            // ------------------
            MATCH (ip_node:%(ip_kind)s {uuid: $node_uuid})
            """ % {
                "ip_kind": InfrahubKind.IPADDRESS
                if isinstance(self.ip_value, IPAddressType)
                else InfrahubKind.IPPREFIX,
            }
            self.add_to_query(get_node_by_id_query)

        else:
            get_node_by_prefix_query = """
            // ------------------
            // Get IP Prefix node by prefix value
            // ------------------
            OPTIONAL MATCH ip_node_path = (:Root)<-[:IS_PART_OF]-(ip_node:%(ip_kind)s)
            -[:HAS_ATTRIBUTE]->(a:Attribute)-[:HAS_VALUE]->(aipn:%(ip_attribute_kind)s),
            (ip_namespace)-[:IS_RELATED]-(nsr:Relationship)
            -[:IS_RELATED]-(ip_node)
            WHERE nsr.name IN ["ip_namespace__ip_prefix", "ip_namespace__ip_address"]
            AND aipn.binary_address = $prefix_binary_full
            AND aipn.prefixlen = $prefixlen
            AND aipn.version = $ip_version
            AND all(r IN relationships(ip_node_path) WHERE (%(branch_filter)s) and r.status = "active")
            """ % {
                "branch_filter": branch_filter,
                "ip_kind": InfrahubKind.IPADDRESS
                if isinstance(self.ip_value, IPAddressType)
                else InfrahubKind.IPPREFIX,
                "ip_attribute_kind": ADDRESS_ATTRIBUTE_LABEL
                if isinstance(self.ip_value, IPAddressType)
                else PREFIX_ATTRIBUTE_LABEL,
            }
            self.add_to_query(get_node_by_prefix_query)

        get_current_parent_query = """
        // ------------------
        // Get prefix node's current parent, if it exists
        // ------------------
        CALL (ip_node) {
            OPTIONAL MATCH parent_prefix_path = (ip_node)-[r1:IS_RELATED]->(:Relationship {name: "parent__child"})-[r2:IS_RELATED]->(current_parent:%(ip_prefix_kind)s)
            WHERE all(r IN relationships(parent_prefix_path) WHERE (%(branch_filter)s))
            RETURN current_parent, (r1.status = "active" AND r2.status = "active") AS parent_is_active
            ORDER BY r1.branch_level DESC, r2.branch_level DESC, r1.from DESC, r2.from DESC
            LIMIT 1
        }
        WITH ip_namespace, ip_node, CASE WHEN parent_is_active THEN current_parent ELSE NULL END as current_parent
        """ % {
            "branch_filter": branch_filter,
            "ip_prefix_kind": InfrahubKind.IPPREFIX,
        }
        self.add_to_query(get_current_parent_query)

        get_current_children_query = """
        // ------------------
        // Get prefix node's current prefix children, if any exist
        // ------------------
        CALL (ip_node) {
            OPTIONAL MATCH child_prefix_path = (ip_node)<-[r1:IS_RELATED]-(:Relationship {name: "parent__child"})<-[r2:IS_RELATED]-(current_prefix_child:%(ip_prefix_kind)s)
            WHERE all(r IN relationships(child_prefix_path) WHERE (%(branch_filter)s))
            WITH current_prefix_child, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY current_prefix_child.uuid, r1.branch_level DESC, r1.from DESC, r2.branch_level DESC, r2.from DESC
            RETURN current_prefix_child, head(collect(is_active)) AS prefix_child_is_active
        }
        WITH ip_namespace, ip_node, current_parent, CASE WHEN prefix_child_is_active THEN current_prefix_child ELSE NULL END as current_prefix_child
        WITH ip_namespace, ip_node, current_parent, collect(current_prefix_child) AS current_prefix_children
        // ------------------
        // Get prefix node's current address children, if any exist
        // ------------------
        CALL (ip_node) {
            OPTIONAL MATCH child_address_path = (ip_node)-[r1:IS_RELATED]-(:Relationship {name: "ip_prefix__ip_address"})-[r2:IS_RELATED]-(current_address_child:%(ip_address_kind)s)
            WHERE all(r IN relationships(child_address_path) WHERE (%(branch_filter)s))
            WITH current_address_child, (r1.status = "active" AND r2.status = "active") AS is_active
            ORDER BY current_address_child.uuid, r1.branch_level DESC, r1.from DESC, r2.branch_level DESC, r2.from DESC
            RETURN current_address_child, head(collect(is_active)) AS address_child_is_active

        }
        WITH ip_namespace, ip_node, current_parent, current_prefix_children, CASE WHEN address_child_is_active THEN current_address_child ELSE NULL END as current_address_child
        WITH ip_namespace, ip_node, current_parent, current_prefix_children, collect(current_address_child) AS current_address_children
        WITH ip_namespace, ip_node, current_parent, current_prefix_children + current_address_children AS current_children
        """ % {
            "branch_filter": branch_filter,
            "ip_prefix_kind": InfrahubKind.IPPREFIX,
            "ip_address_kind": InfrahubKind.IPADDRESS,
        }
        self.add_to_query(get_current_children_query)

        get_new_parent_query = """
        // ------------------
        // Identify the correct parent, if any, for the prefix node
        // ------------------
        CALL (ip_namespace) {
            OPTIONAL MATCH parent_path = (ip_namespace)-[pr1:IS_RELATED {status: "active"}]-(ns_rel:Relationship {name: "ip_namespace__ip_prefix"})
            -[pr2:IS_RELATED {status: "active"}]-(maybe_new_parent:%(ip_prefix_kind)s)
            -[har:HAS_ATTRIBUTE]->(:Attribute {name: "prefix"})
            -[hvr:HAS_VALUE]->(av:%(ip_prefix_attribute_kind)s)
            WHERE all(r IN relationships(parent_path) WHERE (%(branch_filter)s))
            AND av.version = $ip_version
            AND av.binary_address IN $possible_prefix_list
            AND any(prefix_and_length IN $possible_prefix_and_length_list WHERE av.binary_address = prefix_and_length[0] AND av.prefixlen <= prefix_and_length[1])
            WITH
                maybe_new_parent,
                har,
                hvr,
                av.prefixlen as prefixlen,
                (har.status = "active" AND hvr.status = "active") AS is_active,
                har.branch_level + hvr.branch_level AS branch_level
            ORDER BY branch_level DESC, har.from DESC, hvr.from DESC
            WITH maybe_new_parent, prefixlen, is_active
            RETURN maybe_new_parent, head(collect(prefixlen)) AS mnp_prefixlen, head(collect(is_active)) AS mnp_is_active
        }
        WITH ip_namespace, ip_node, current_parent, current_children, mnp_prefixlen,
            CASE WHEN mnp_is_active THEN maybe_new_parent ELSE NULL END AS maybe_new_parent
        WITH ip_namespace, ip_node, current_parent, current_children, maybe_new_parent, mnp_prefixlen
        ORDER BY ip_node.uuid, mnp_prefixlen DESC
        WITH ip_namespace, ip_node, current_parent, current_children, head(collect(maybe_new_parent)) as new_parent
        """ % {
            "branch_filter": branch_filter,
            "ip_prefix_kind": InfrahubKind.IPPREFIX,
            "ip_prefix_attribute_kind": PREFIX_ATTRIBUTE_LABEL,
        }
        self.add_to_query(get_new_parent_query)

        get_new_children_query = """
        // ------------------
        // Identify the correct children, if any, for the prefix node
        // ------------------
        CALL (ip_namespace, ip_node) {
            // Get ALL possible children for the prefix node
            OPTIONAL MATCH child_path = (
                 (ip_namespace)-[r1:IS_RELATED]
                 -(ns_rel:Relationship)-[r2:IS_RELATED]
                 -(maybe_new_child:Node)-[har:HAS_ATTRIBUTE]
                 ->(a:Attribute)-[hvr:HAS_VALUE]
                 ->(av:AttributeValue)
            )
            WHERE $is_prefix  // only prefix nodes can have children
            AND ns_rel.name IN ["ip_namespace__ip_prefix", "ip_namespace__ip_address"]
            AND any(child_kind IN [$ip_prefix_kind, $ip_address_kind] WHERE child_kind IN labels(maybe_new_child))
            AND a.name in ["prefix", "address"]
            AND any(attr_kind IN [$ip_prefix_attribute_kind, $ip_address_attribute_kind] WHERE attr_kind IN labels(av))
            AND (ip_node IS NULL OR maybe_new_child.uuid <> ip_node.uuid)
            AND (
                ($ip_prefix_kind IN labels(maybe_new_child) AND av.prefixlen > $prefixlen)
                OR ($ip_address_kind IN labels(maybe_new_child) AND av.prefixlen >= $prefixlen)
            )
            AND av.version = $ip_version
            AND av.binary_address STARTS WITH $prefix_binary_host
            AND all(r IN relationships(child_path) WHERE (%(branch_filter)s))
            WITH
                maybe_new_child,
                av AS mnc_attribute,
                r1,
                r2,
                har,
                hvr,
                all(r in relationships(child_path) WHERE r.status = "active") AS is_active,
                reduce(br_lvl = 0, r in relationships(child_path) | br_lvl + r.branch_level) AS branch_level
            ORDER BY maybe_new_child.uuid, branch_level DESC, hvr.from DESC, har.from DESC, r2.from DESC, r1.from DESC
            WITH maybe_new_child, head(collect([mnc_attribute, is_active])) AS latest_mnc_details
            RETURN maybe_new_child, latest_mnc_details[0] AS latest_mnc_attribute, latest_mnc_details[1] AS mnc_is_active
        }
        WITH ip_namespace, ip_node, current_parent, current_children, new_parent, latest_mnc_attribute,
            CASE WHEN mnc_is_active IN [TRUE, NULL] THEN maybe_new_child ELSE NULL END AS maybe_new_child
        WITH ip_namespace, ip_node, current_parent, current_children, new_parent, collect([maybe_new_child, latest_mnc_attribute]) AS maybe_children_ips
        WITH ip_namespace, ip_node, current_parent, current_children, new_parent, maybe_children_ips, range(0, size(maybe_children_ips) - 1) AS child_indices
        UNWIND child_indices as ind
        CALL (ind, maybe_children_ips) {
            // ------------------
            // Filter all possible children to remove those that have a more-specific parent
            // among the list of all possible children
            // ------------------
            WITH ind, maybe_children_ips AS ips
            RETURN REDUCE(
                has_more_specific_parent = FALSE, potential_parent IN ips |
                CASE
                    WHEN has_more_specific_parent THEN has_more_specific_parent  // keep it True once set
                    WHEN potential_parent IS NULL OR ips[ind][0] IS NULL THEN has_more_specific_parent
                    WHEN potential_parent[0] = ips[ind][0] THEN has_more_specific_parent  // skip comparison to self
                    WHEN $ip_address_kind in labels(potential_parent[0]) THEN has_more_specific_parent  // address cannot be a parent
                    WHEN $ip_prefix_attribute_kind IN labels(ips[ind][1]) AND (potential_parent[1]).prefixlen >= (ips[ind][1]).prefixlen THEN has_more_specific_parent  // prefix with same or greater prefixlen for prefix cannot be parent
                    WHEN $ip_address_attribute_kind IN labels(ips[ind][1]) AND (potential_parent[1]).prefixlen > (ips[ind][1]).prefixlen THEN has_more_specific_parent  // prefix with greater prefixlen for address cannot be parent
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
        """ % {
            "branch_filter": branch_filter,
        }
        self.add_to_query(get_new_children_query)
        self.return_labels = ["ip_node", "current_parent", "current_children", "new_parent", "new_children"]

    def _get_uuid_from_query(self, node_name: str) -> str | None:
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

    def get_ip_node_uuid(self) -> str | None:
        return self._get_uuid_from_query("ip_node")

    def get_current_parent_uuid(self) -> str | None:
        return self._get_uuid_from_query("current_parent")

    def get_calculated_parent_uuid(self) -> str | None:
        return self._get_uuid_from_query("new_parent")

    def get_current_children_uuids(self) -> list[str]:
        return self._get_uuids_from_query_list("current_children")

    def get_calculated_children_uuids(self) -> list[str]:
        return self._get_uuids_from_query_list("new_children")
