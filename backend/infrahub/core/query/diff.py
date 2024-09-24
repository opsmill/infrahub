from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from infrahub.core.constants import BranchSupportType
from infrahub.core.query import Query, QueryResult, QueryType, sort_results_by_time
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class DiffQuery(Query):
    branch_names: list[str]
    diff_from: Timestamp
    diff_to: Timestamp
    type: QueryType = QueryType.READ

    def __init__(
        self,
        branch: Branch,
        diff_from: Union[Timestamp, str] = None,
        diff_to: Union[Timestamp, str] = None,
        **kwargs,
    ):
        """A diff is always in the context of a branch"""

        if not diff_from and branch.is_default:
            raise ValueError("diff_from is mandatory when the diff is on the main branch.")

        # If diff from hasn't been provided, we'll use the creation of the branch as the starting point
        if diff_from:
            self.diff_from = Timestamp(diff_from)
        else:
            self.diff_from = Timestamp(branch.created_at)

        # If Diff_to is not defined it will automatically select the current time.
        self.diff_to = Timestamp(diff_to)

        if self.diff_to < self.diff_from:
            raise ValueError("diff_to must be later than diff_from")

        self.branch_names = branch.get_branches_in_scope()

        super().__init__(branch, **kwargs)


class DiffNodeQuery(DiffQuery):
    name: str = "diff_node"

    def __init__(
        self,
        namespaces_include: Optional[list[str]] = None,
        namespaces_exclude: Optional[list[str]] = None,
        kinds_include: Optional[list[str]] = None,
        kinds_exclude: Optional[list[str]] = None,
        branch_support: Optional[list[BranchSupportType]] = None,
        **kwargs,
    ):
        self.namespaces_include = namespaces_include
        self.namespaces_exclude = namespaces_exclude
        self.kinds_include = kinds_include
        self.kinds_exclude = kinds_exclude
        self.branch_support = branch_support or [BranchSupportType.AWARE]

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs):
        # TODO need to improve the query to capture an object that has been deleted into the branch
        # TODO probably also need to consider a node what was merged already

        br_filter, br_params = self.branch.get_query_filter_range(
            rel_label="r",
            start_time=self.diff_from,
            end_time=self.diff_to,
        )

        self.params.update(br_params)
        self.params["branch_support"] = [item.value for item in self.branch_support]

        where_clause = ""
        if self.namespaces_include:
            where_clause += "n.namespace IN $namespaces_include AND "
            self.params["namespaces_include"] = self.namespaces_include

        if self.namespaces_exclude:
            where_clause += "NOT(n.namespace IN $namespaces_exclude) AND "
            self.params["namespaces_exclude"] = self.namespaces_exclude

        if self.kinds_include:
            where_clause += "n.kind IN $kinds_include AND "
            self.params["kinds_include"] = self.kinds_include

        if self.kinds_exclude:
            where_clause += "NOT(n.kind IN $kinds_exclude) AND "
            self.params["kinds_exclude"] = self.kinds_exclude

        where_clause += "n.branch_support IN $branch_support AND %s" % "\n AND ".join(br_filter)

        query = (
            """
        MATCH (root:Root)-[r:IS_PART_OF]-(n:Node)
        WHERE %s
        """
            % where_clause
        )

        self.add_to_query(query)
        self.order_by = ["n.uuid"]

        self.return_labels = ["n", "r"]


class DiffAttributeQuery(DiffQuery):
    name: str = "diff_attribute"

    def __init__(
        self,
        namespaces_include: Optional[list[str]] = None,
        namespaces_exclude: Optional[list[str]] = None,
        kinds_include: Optional[list[str]] = None,
        kinds_exclude: Optional[list[str]] = None,
        branch_support: Optional[list[BranchSupportType]] = None,
        **kwargs,
    ):
        self.namespaces_include = namespaces_include
        self.namespaces_exclude = namespaces_exclude
        self.kinds_include = kinds_include
        self.kinds_exclude = kinds_exclude
        self.branch_support = branch_support or [BranchSupportType.AWARE]

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs):
        # TODO need to improve the query to capture an object that has been deleted into the branch

        rels_filters, rels_params = self.branch.get_query_filter_relationships_diff(
            rel_labels=["r2"], diff_from=self.diff_from, diff_to=self.diff_to
        )

        self.params.update(rels_params)
        self.params["branch_support"] = [item.value for item in self.branch_support]

        where_clause = ""
        if self.namespaces_include:
            where_clause += "n.namespace IN $namespaces_include AND "
            self.params["namespaces_include"] = self.namespaces_include

        if self.namespaces_exclude:
            where_clause += "NOT(n.namespace IN $namespaces_exclude) AND "
            self.params["namespaces_exclude"] = self.namespaces_exclude

        if self.kinds_include:
            where_clause += "n.kind IN $kinds_include AND "
            self.params["kinds_include"] = self.kinds_include

        if self.kinds_exclude:
            where_clause += "NOT(n.kind IN $kinds_exclude) AND "
            self.params["kinds_exclude"] = self.kinds_exclude

        where_clause += "a.branch_support IN $branch_support AND %s" % "\n AND ".join(rels_filters)

        query = (
            """
        MATCH (n:Node)-[r1:HAS_ATTRIBUTE]-(a:Attribute)-[r2:HAS_VALUE|IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]->(ap)
        WHERE %s
        """
            % where_clause
        )

        self.add_to_query(query)

        self.return_labels = ["n", "a", "ap", "r1", "r2"]


class DiffRelationshipQuery(DiffQuery):
    name: str = "diff_relationship"
    type: QueryType = QueryType.READ

    def __init__(
        self,
        namespaces_include: Optional[list[str]] = None,
        namespaces_exclude: Optional[list[str]] = None,
        kinds_include: Optional[list[str]] = None,
        kinds_exclude: Optional[list[str]] = None,
        branch_support: Optional[list[BranchSupportType]] = None,
        **kwargs,
    ):
        self.namespaces_include = namespaces_include
        self.namespaces_exclude = namespaces_exclude
        self.kinds_include = kinds_include
        self.kinds_exclude = kinds_exclude
        self.branch_support = branch_support or [BranchSupportType.AWARE]

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs):
        where_clause = ""
        if self.namespaces_include:
            where_clause += "(src.namespace IN $namespaces_include OR dst.namespace IN $namespaces_include) AND "
            self.params["namespaces_include"] = self.namespaces_include

        if self.namespaces_exclude:
            where_clause += "NOT(src.namespace IN $namespaces_exclude OR dst.namespace IN $namespaces_exclude) AND "
            self.params["namespaces_exclude"] = self.namespaces_exclude

        if self.kinds_include:
            where_clause += "(src.kind IN $kinds_include OR dst.kind IN $kinds_include) AND "
            self.params["kinds_include"] = self.kinds_include

        if self.kinds_exclude:
            where_clause += "NOT(src.kind IN $kinds_exclude OR dst.kind IN $kinds_exclude) AND "
            self.params["kinds_exclude"] = self.kinds_exclude

        query = (
            """
        CALL {
            MATCH p = ((src:Node)-[r1:IS_RELATED]-(rel:Relationship)-[r2:IS_RELATED]-(dst:Node))
            WHERE (rel.branch_support IN $branch_support AND %s r1.branch = r2.branch AND
                (r1.to = r2.to OR (r1.to is NULL AND r2.to is NULL)) AND r1.from = r2.from AND r1.status = r2.status
                AND all(r IN relationships(p) WHERE (r.branch IN $branch_names AND r.from >= $diff_from AND r.from <= $diff_to
                    AND ((r.to >= $diff_from AND r.to <= $diff_to) OR r.to is NULL))
                )
            )
            RETURN DISTINCT [rel.uuid, r1.branch] as identifier, rel, r1.branch as branch_name
        }
        CALL {
            WITH rel, branch_name
            MATCH p = ((sn:Node)-[r1:IS_RELATED]-(rel:Relationship)-[r2:IS_RELATED]-(dn:Node))
            WHERE (rel.branch_support IN $branch_support AND r1.branch = r2.branch AND
                (r1.to = r2.to OR (r1.to is NULL AND r2.to is NULL)) AND r1.from = r2.from AND r1.status = r2.status
                AND all(r IN relationships(p) WHERE (r.branch = branch_name AND r.from >= $diff_from AND r.from <= $diff_to
                    AND ((r.to >= $diff_from AND r.to <= $diff_to) OR r.to is NULL))
                )
            )
            AND sn <> dn
            RETURN rel as rel1, sn as sn1, dn as dn1, r1 as r11, r2 as r21
            ORDER BY r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH rel1 as rel, sn1 as sn, dn1 as dn, r11 as r1, r21 as r2
        """
            % where_clause
        )

        self.add_to_query(query)
        self.params["branch_names"] = self.branch_names
        self.params["diff_from"] = self.diff_from.to_string()
        self.params["diff_to"] = self.diff_to.to_string()
        self.params["branch_support"] = [item.value for item in self.branch_support]

        self.return_labels = ["sn", "dn", "rel", "r1", "r2"]


class DiffRelationshipPropertyQuery(DiffQuery):
    name: str = "diff_relationship_property"
    type: QueryType = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs):
        rels_filter, rels_params = self.branch.get_query_filter_relationships_range(
            rel_labels=["r"], start_time=self.diff_from, end_time=self.diff_to
        )
        self.params.update(rels_params)

        query = """
        CALL {
            MATCH (rel:Relationship)-[r3:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]-()
            WHERE (r3.branch IN $branch_names AND r3.from >= $diff_from AND r3.from <= $diff_to
            AND ((r3.to >= $diff_from AND r3.to <= $diff_to ) OR r3.to is NULL))
            RETURN DISTINCT rel
        }
        CALL {
            WITH rel
            MATCH p = ((sn:Node)-[r1]-(rel)-[r2]-(dn:Node))
            WHERE r1.branch = r2.branch AND (r1.to = r2.to OR (r1.to is NULL AND r2.to is NULL))
            AND r1.from = r2.from AND r1.status = r2.status AND all(r IN relationships(p) WHERE ( %s ))
            AND sn <> dn
            RETURN rel as rel1, sn as sn1, dn as dn1, r1 as r11, r2 as r21
            ORDER BY r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH rel1 as rel, sn1 as sn, dn1 as dn, r11 as r1, r21 as r2
        MATCH (rel:Relationship)-[r3:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]-(rp)
        WHERE (
            r3.branch IN $branch_names AND r3.from >= $diff_from AND r3.from <= $diff_to
            AND ((r3.to >= $diff_from AND r3.to <= $diff_to) OR r3.to is NULL)
        )
        """ % "\n AND ".join(rels_filter)

        self.add_to_query(query)
        self.params["branch_names"] = self.branch_names
        self.params["diff_from"] = self.diff_from.to_string()
        self.params["diff_to"] = self.diff_to.to_string()

        self.return_labels = ["sn", "dn", "rel", "rp", "r3", "r1", "r2"]


class DiffNodePropertiesByIDSRangeQuery(Query):
    name: str = "diff_node_properties_range_ids"

    def __init__(self, ids: list[str], diff_from: str, diff_to: str, account=None, **kwargs):
        self.account = account
        self.ids = ids
        self.time_from = Timestamp(diff_from)
        self.time_to = Timestamp(diff_to)

        super().__init__(order_by=["a.name"], **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs):
        self.params["ids"] = self.ids

        rels_filter, rels_params = self.branch.get_query_filter_relationships_range(
            rel_labels=["r"], start_time=self.time_from, end_time=self.time_to, include_outside_parentheses=True
        )

        self.params.update(rels_params)

        query = """
        MATCH (a) WHERE a.uuid IN $ids
        MATCH (a)-[r:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER|HAS_VALUE]-(ap)
        WHERE %s
        """ % ("\n AND ".join(rels_filter),)

        self.add_to_query(query)
        self.return_labels = ["a", "ap", "r"]

    def get_results_by_id_and_prop_type(self, attr_id: str, prop_type: str) -> list[QueryResult]:
        """Return a list of all results matching a given relationship id / property type.

        The results are ordered chronologicall (from oldest to newest)
        """
        results = [
            result
            for result in self.results
            if result.get("r").get("branch") in self.branch.get_branches_in_scope()
            and result.get("a").get("uuid") == attr_id
            and result.get("r").type == prop_type
        ]

        return sort_results_by_time(results, rel_label="r")


class DiffNodePropertiesByIDSQuery(Query):
    name: str = "diff_node_properties_ids"
    order_by: list[str] = ["a.name"]

    def __init__(
        self,
        ids: list[str],
        at: str,
        account=None,
        **kwargs,
    ):
        self.account = account
        self.ids = ids
        self.at = Timestamp(at)

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs):
        self.params["ids"] = self.ids

        rels_filter, rels_params = self.branch.get_query_filter_relationships(
            rel_labels=["r"], at=self.at, include_outside_parentheses=True
        )

        self.params.update(rels_params)

        query = """
        MATCH (a:Attribute) WHERE a.uuid IN $ids
        MATCH (a)-[r:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER|HAS_VALUE]-(ap)
        WHERE %s
        """ % ("\n AND ".join(rels_filter),)

        self.add_to_query(query)
        self.return_labels = ["a", "ap", "r"]

    def get_results_by_id_and_prop_type(self, attr_id: str, prop_type: str) -> list[QueryResult]:
        """Return a list of all results matching a given relationship id / property type.

        The results are ordered chronologicall (from oldest to newest)
        """
        results = [
            result
            for result in self.results
            if result.get("r").get("branch") in self.branch.get_branches_in_scope()
            and result.get("a").get("uuid") == attr_id
            and result.get("r").type == prop_type
        ]

        return sort_results_by_time(results, rel_label="r")


class DiffRelationshipPropertiesByIDSRangeQuery(Query):
    name = "diff_relationship_properties_range_ids"

    type: QueryType = QueryType.READ

    def __init__(
        self,
        ids: list[str],
        diff_from: str,
        diff_to: str,
        account=None,
        **kwargs,
    ):
        self.account = account
        self.ids = ids
        self.time_from = Timestamp(diff_from)
        self.time_to = Timestamp(diff_to)

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs):
        self.params["ids"] = self.ids

        rels_filter, rels_params = self.branch.get_query_filter_relationships_range(
            rel_labels=["r"], start_time=self.time_from, end_time=self.time_to, include_outside_parentheses=True
        )

        self.params.update(rels_params)

        # TODO Compute the list of potential relationship dynamically in the future based on the class
        query = """
        MATCH (rl:Relationship) WHERE rl.uuid IN $ids
        MATCH (rl)-[r:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]-(rp)
        WHERE %s
        """ % ("\n AND ".join(rels_filter),)

        self.params["at"] = self.at.to_string()

        self.add_to_query(query)
        self.return_labels = ["rl", "rp", "r"]

    def get_results_by_id_and_prop_type(self, rel_id: str, prop_type: str) -> list[QueryResult]:
        """Return a list of all results matching a given relationship id / property type.
        The results are ordered chronologically
        """
        results = [
            result
            for result in self.results
            if result.get("r").get("branch") in self.branch.get_branches_in_scope()
            and result.get("rl").get("uuid") == rel_id
            and result.get("r").type == prop_type
        ]

        return sort_results_by_time(results, rel_label="r")


class DiffCountChanges(Query):
    name: str = "diff_count_changes"
    type: QueryType = QueryType.READ

    def __init__(
        self,
        branch_names: list[str],
        diff_from: Timestamp,
        diff_to: Timestamp,
        **kwargs,
    ):
        self.branch_names = branch_names
        self.diff_from = diff_from
        self.diff_to = diff_to
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs):
        self.params = {
            "from_time": self.diff_from.to_string(),
            "to_time": self.diff_to.to_string(),
            "branch_names": self.branch_names,
        }
        query = """
        MATCH (p)-[diff_rel]-(q)
        WHERE any(l in labels(p) WHERE l in ["Node", "Attribute", "Relationship"])
        AND diff_rel.branch in $branch_names
        AND (
            (diff_rel.from >= $from_time AND diff_rel.from <= $to_time)
            OR (diff_rel.to >= $to_time AND diff_rel.to <= $to_time)
        )
        AND (p.branch_support = "aware" OR q.branch_support = "aware")
        WITH diff_rel.branch AS branch_name, count(*) AS num_changes
        """
        self.add_to_query(query=query)
        self.return_labels = ["branch_name", "num_changes"]

    def get_num_changes_by_branch(self) -> dict[str, int]:
        branch_count_map = {}
        for result in self.get_results():
            branch_name = str(result.get("branch_name"))
            try:
                count = int(result.get("num_changes"))
            except (TypeError, ValueError):
                count = 0
            branch_count_map[branch_name] = count
        for branch_name in self.branch_names:
            if branch_name not in branch_count_map:
                branch_count_map[branch_name] = 0
        return branch_count_map


class DiffAllPathsQuery(DiffQuery):
    """Gets the required Cypher paths for a diff"""

    name: str = "diff_node"

    def __init__(
        self,
        base_branch: Branch,
        diff_branch_create_time: Timestamp,
        branch_support: list[BranchSupportType] | None = None,
        current_node_field_specifiers: list[tuple[str, str]] | None = None,
        new_node_field_specifiers: list[tuple[str, str]] | None = None,
        *args,
        **kwargs,
    ):
        self.base_branch = base_branch
        self.diff_branch_create_time = diff_branch_create_time
        self.branch_support = branch_support or [BranchSupportType.AWARE]
        self.current_node_field_specifiers = current_node_field_specifiers
        self.new_node_field_specifiers = new_node_field_specifiers

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs):
        from_str = self.diff_from.to_string()
        self.params.update(
            {
                "base_branch_name": self.base_branch.name,
                "branch_name": self.branch.name,
                "branch_create_time": self.diff_branch_create_time.to_string(),
                "from_time": from_str,
                "to_time": self.diff_to.to_string(),
                "branch_support": [item.value for item in self.branch_support],
                "new_node_field_specifiers": self.new_node_field_specifiers,
                "current_node_field_specifiers": self.current_node_field_specifiers,
            }
        )
        query = """
WITH CASE
    WHEN $new_node_field_specifiers IS NULL AND $current_node_field_specifiers IS NULL THEN [[NULL, $from_time]]
    WHEN $new_node_field_specifiers IS NULL OR size($new_node_field_specifiers) = 0 THEN [[$current_node_field_specifiers, $from_time]]
    WHEN $current_node_field_specifiers IS NULL OR size($current_node_field_specifiers) = 0 THEN [[$new_node_field_specifiers, $branch_create_time]]
    ELSE [[$new_node_field_specifiers, $branch_create_time], [$current_node_field_specifiers, $from_time]]
END AS diff_filter_params_list
UNWIND diff_filter_params_list AS diff_filter_params
CALL {
    WITH diff_filter_params
    WITH diff_filter_params[0] AS node_field_specifiers_list, diff_filter_params[1] AS from_time
    CALL {
        WITH node_field_specifiers_list, from_time
        WITH reduce(node_ids = [], nfs IN node_field_specifiers_list | node_ids + [nfs[0]]) AS node_ids_list, from_time
        // -------------------------------------
        // Identify nodes added/removed on branch
        // -------------------------------------
        MATCH (q:Root)<-[diff_rel:IS_PART_OF {branch: $branch_name}]-(p:Node)
        WHERE (node_ids_list IS NULL OR p.uuid IN node_ids_list)
        AND (from_time <= diff_rel.from < $to_time)
        AND (diff_rel.to IS NULL OR (from_time <= diff_rel.to < $to_time))
        AND (p.branch_support IN $branch_support OR q.branch_support IN $branch_support)
        WITH p, q, diff_rel
        // -------------------------------------
        // Get every path on this branch under each node
        // -------------------------------------
        CALL {
            WITH p, q, diff_rel
            OPTIONAL MATCH path = (
                (q)<-[top_diff_rel:IS_PART_OF]-(p)-[r_node]-(node)-[r_prop]-(prop)
            )
            WHERE %(id_func)s(diff_rel) = %(id_func)s(top_diff_rel)
            AND type(r_node) IN ["HAS_ATTRIBUTE", "IS_RELATED"]
            AND any(l in labels(node) WHERE l in ["Attribute", "Relationship"])
            AND type(r_prop) IN ["IS_VISIBLE", "IS_PROTECTED", "HAS_SOURCE", "HAS_OWNER", "HAS_VALUE", "IS_RELATED"]
            AND any(l in labels(prop) WHERE l in ["Boolean", "Node", "AttributeValue"])
            AND ALL(
                r in [r_node, r_prop]
                WHERE r.from <= $to_time AND r.branch = top_diff_rel.branch
            )
            AND top_diff_rel.from <= r_node.from
            AND (top_diff_rel.to IS NULL OR top_diff_rel.to >= r_node.from)
            AND r_node.from <= r_prop.from
            AND (r_node.to IS NULL OR r_node.to >= r_prop.from)
            AND [%(id_func)s(p), type(r_node)] <> [%(id_func)s(prop), type(r_prop)]
            AND top_diff_rel.status = r_node.status
            AND top_diff_rel.status = r_prop.status
            WITH path, node, prop, r_prop, r_node
            ORDER BY
                %(id_func)s(node),
                %(id_func)s(prop),
                r_prop.from DESC,
                r_node.from DESC
            WITH node, prop, type(r_prop) AS r_prop_type, type(r_node) AS r_node_type, head(collect(path)) AS top_diff_path
            RETURN top_diff_path
        }
        RETURN top_diff_path AS diff_path
    }
    RETURN diff_path
    UNION
    WITH diff_filter_params
    WITH diff_filter_params[0] AS node_field_specifiers_list, diff_filter_params[1] AS from_time
    CALL {
        WITH node_field_specifiers_list, from_time
        // -------------------------------------
        // Identify attributes/relationships added/removed on branch
        // -------------------------------------
        CALL {
            WITH node_field_specifiers_list, from_time
            MATCH (root:Root)<-[r_root:IS_PART_OF]-(p:Node)-[diff_rel:HAS_ATTRIBUTE {branch: $branch_name}]->(q:Attribute)
            // exclude attributes and relationships under added/removed nodes b/c they are covered above
            WHERE (node_field_specifiers_list IS NULL OR [p.uuid, q.name] IN node_field_specifiers_list)
            AND r_root.branch IN [$branch_name, $base_branch_name]
            AND r_root.from < from_time
            AND r_root.status = "active"
            // get attributes and relationships added on the branch during the timeframe
            AND (from_time <= diff_rel.from < $to_time)
            AND (diff_rel.to IS NULL OR (from_time <= diff_rel.to < $to_time))
            AND r_root.from <= diff_rel.from
            AND (r_root.to IS NULL OR r_root.to >= diff_rel.from)
            AND (p.branch_support IN $branch_support OR q.branch_support IN $branch_support)
            RETURN root, r_root, p, diff_rel, q
            UNION ALL
            WITH node_field_specifiers_list, from_time
            MATCH (root:Root)<-[r_root:IS_PART_OF]-(p:Node)-[diff_rel:IS_RELATED {branch: $branch_name}]-(q:Relationship)
            // exclude attributes and relationships under added/removed nodes b/c they are covered above
            WHERE (node_field_specifiers_list IS NULL OR [p.uuid, q.name] IN node_field_specifiers_list)
            AND r_root.branch IN [$branch_name, $base_branch_name]
            AND r_root.from < from_time
            AND r_root.status = "active"
            // get attributes and relationships added on the branch during the timeframe
            AND (from_time <= diff_rel.from < $to_time)
            AND (diff_rel.to IS NULL OR (from_time <= diff_rel.to < $to_time))
            AND r_root.from <= diff_rel.from
            AND (r_root.to IS NULL OR r_root.to >= diff_rel.from)
            AND (p.branch_support IN $branch_support OR q.branch_support IN $branch_support)
            RETURN root, r_root, p, diff_rel, q
        }
        WITH root, r_root, p, diff_rel, q
        // -------------------------------------
        // Get every path on this branch under each attribute/relationship
        // -------------------------------------
        CALL {
            WITH root, r_root, p, diff_rel, q
            OPTIONAL MATCH path = (
                (root:Root)<-[mid_r_root:IS_PART_OF]-(p)-[mid_diff_rel]-(q)-[r_prop]-(prop)
            )
            WHERE %(id_func)s(mid_r_root) =  %(id_func)s(r_root)
            AND %(id_func)s(mid_diff_rel) =  %(id_func)s(diff_rel)
            AND type(r_prop) IN ["IS_VISIBLE", "IS_PROTECTED", "HAS_SOURCE", "HAS_OWNER", "HAS_VALUE", "IS_RELATED"]
            AND any(l in labels(prop) WHERE l in ["Boolean", "Node", "AttributeValue"])
            AND r_prop.from <= $to_time AND r_prop.branch = mid_diff_rel.branch
            AND mid_diff_rel.from <= r_prop.from
            AND (mid_diff_rel.to IS NULL OR mid_diff_rel.to >= r_prop.from)
            AND [%(id_func)s(p), type(mid_diff_rel)] <> [%(id_func)s(prop), type(r_prop)]
            // exclude paths where an active edge is below a deleted edge
            AND (mid_diff_rel.status = "active" OR r_prop.status = "deleted")
            WITH path, prop, r_prop, mid_r_root
            ORDER BY
                type(r_prop),
                mid_r_root.branch = mid_diff_rel.branch DESC,
                r_prop.from DESC,
                mid_r_root.from DESC
            WITH prop, type(r_prop) AS type_r_prop, head(collect(path)) AS latest_prop_path
            RETURN latest_prop_path
        }
        RETURN latest_prop_path AS mid_diff_path
    }
    RETURN mid_diff_path AS diff_path
    UNION
    WITH diff_filter_params
    WITH diff_filter_params[0] AS node_field_specifiers_list, diff_filter_params[1] AS from_time
    CALL {
        WITH node_field_specifiers_list, from_time
        // -------------------------------------
        // Identify properties added/removed on branch
        // -------------------------------------
        MATCH diff_rel_path = (root:Root)<-[r_root:IS_PART_OF]-(n:Node)-[r_node]-(p)-[diff_rel {branch: $branch_name}]->(q)
        WHERE (node_field_specifiers_list IS NULL OR [n.uuid, p.name] IN node_field_specifiers_list)
        AND (from_time <= diff_rel.from < $to_time)
        AND (diff_rel.to IS NULL OR (from_time <= diff_rel.to < $to_time))
        // exclude attributes and relationships under added/removed nodes, attrs, and rels b/c they are covered above
        AND ALL(
            r in [r_root, r_node]
            WHERE r.from <= from_time AND r.branch IN [$branch_name, $base_branch_name]
        )
        AND (p.branch_support IN $branch_support OR q.branch_support IN $branch_support)
        AND any(l in labels(p) WHERE l in ["Attribute", "Relationship"])
        AND type(diff_rel) IN ["IS_VISIBLE", "IS_PROTECTED", "HAS_SOURCE", "HAS_OWNER", "HAS_VALUE"]
        AND any(l in labels(q) WHERE l in ["Boolean", "Node", "AttributeValue"])
        AND type(r_node) IN ["HAS_ATTRIBUTE", "IS_RELATED"]
        AND ALL(
            r_pair IN [[r_root, r_node], [r_node, diff_rel]]
            // filter out paths where a base branch edge follows a branch edge
            WHERE ((r_pair[0]).branch = $base_branch_name OR (r_pair[1]).branch = $branch_name)
            // filter out paths where an active edge follows a deleted edge
            AND ((r_pair[0]).status = "active" OR (r_pair[1]).status = "deleted")
            // filter out paths where an earlier from time follows a later from time
            AND (r_pair[0]).from <= (r_pair[1]).from
            // require adjacent edge pairs to have overlapping times, but only if on the same branch
            AND (
                (r_pair[0]).branch <> (r_pair[1]).branch
                OR (r_pair[0]).to IS NULL
                OR (r_pair[0]).to >= (r_pair[1]).from
            )
        )
        AND [%(id_func)s(n), type(r_node)] <> [%(id_func)s(q), type(diff_rel)]
        WITH diff_rel_path, r_root, n, r_node, p, diff_rel
        ORDER BY
            %(id_func)s(n) DESC,
            %(id_func)s(p) DESC,
            type(diff_rel),
            r_node.branch = diff_rel.branch DESC,
            r_root.branch = diff_rel.branch DESC,
            diff_rel.from DESC,
            r_node.from DESC,
            r_root.from DESC
        // -------------------------------------
        // Add base branch paths, if they exist, to capture previous values
        // Add peer-side of any relationships to get the peer's ID
        // -------------------------------------
        WITH n, p, type(diff_rel) AS drt, head(collect(diff_rel_path)) AS deepest_diff_path
        CALL {
            WITH n, p, deepest_diff_path
            WITH n, p, deepest_diff_path AS diff_rel_path, relationships(deepest_diff_path) AS drp_relationships
            WITH n, p, diff_rel_path, drp_relationships[2] as diff_rel, drp_relationships[0] AS r_root, drp_relationships[1] AS r_node
            // get base branch version of the diff path, if it exists
            WITH diff_rel_path, diff_rel, r_root, n, r_node, p
            OPTIONAL MATCH latest_base_path = (:Root)<-[deep_r_root]-(n)-[deep_r_node]-(p)-[base_diff_rel]->(base_prop)
            WHERE %(id_func)s(deep_r_node) = %(id_func)s(r_node)
            AND %(id_func)s(deep_r_root) = %(id_func)s(r_root)
            AND %(id_func)s(n) <> %(id_func)s(base_prop)
            AND type(base_diff_rel) = type(diff_rel)
            AND all(
                r in relationships(latest_base_path)
                WHERE r.branch = $base_branch_name AND r.from <= $branch_create_time
            )
            WITH diff_rel_path, latest_base_path, diff_rel, r_root, n, r_node, p
            ORDER BY base_diff_rel.from DESC, r_node.from DESC, r_root.from DESC
            LIMIT 1
            // get peer node for updated relationship properties
            WITH diff_rel_path, latest_base_path, diff_rel, r_root, n, r_node, p
            OPTIONAL MATCH base_peer_path = (
                (:Root)<-[base_r_root]-(n)-[base_r_node]-(p:Relationship)-[base_r_peer:IS_RELATED]-(base_peer:Node)
            )
            WHERE type(diff_rel) <> "IS_RELATED"
            AND %(id_func)s(base_r_root) = %(id_func)s(r_root)
            AND %(id_func)s(base_r_node) = %(id_func)s(r_node)
            AND [%(id_func)s(n), type(base_r_node)] <> [%(id_func)s(base_peer), type(base_r_peer)]
            AND base_r_peer.from <= $to_time
            // filter out paths where an earlier from time follows a later from time
            AND base_r_node.from <= base_r_peer.from
            // filter out paths where a base branch edge follows a branch edge
            AND (base_r_node.branch = $base_branch_name OR base_r_peer.branch = $branch_name)
            // filter out paths where an active edge follows a deleted edge
            AND (base_r_node.status = "active" OR base_r_peer.status = "deleted")
            // require adjacent edge pairs to have overlapping times, but only if on the same branch
            AND (
                base_r_node.branch <> base_r_peer.branch
                OR base_r_node.to IS NULL
                OR base_r_node.to >= base_r_peer.from
            )
            WITH diff_rel_path, latest_base_path, base_peer_path, base_r_peer, diff_rel
            ORDER BY base_r_peer.branch = diff_rel.branch DESC, base_r_peer.from DESC
            LIMIT 1
            RETURN latest_base_path, base_peer_path
        }
        WITH reduce(
            diff_rel_paths = [], item IN [deepest_diff_path, latest_base_path, base_peer_path] |
            CASE WHEN item IS NULL THEN diff_rel_paths ELSE diff_rel_paths + [item] END
        ) AS diff_rel_paths
        UNWIND diff_rel_paths AS bottom_diff_path
        RETURN bottom_diff_path
    }
    RETURN bottom_diff_path AS diff_path
}
        """ % {"id_func": db.get_id_function_name()}
        self.add_to_query(query)
        self.return_labels = ["DISTINCT diff_path AS diff_path"]
