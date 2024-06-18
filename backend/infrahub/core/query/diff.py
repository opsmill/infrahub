from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from infrahub.core import registry
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


class DiffAllPathsQuery(DiffQuery):
    """Gets the required Cypher paths for a diff"""

    name: str = "diff_node"

    def __init__(
        self,
        base_branch: Branch,
        namespaces_include: Optional[List[str]] = None,
        namespaces_exclude: Optional[List[str]] = None,
        kinds_include: Optional[List[str]] = None,
        kinds_exclude: Optional[List[str]] = None,
        branch_support: Optional[List[BranchSupportType]] = None,
        *args,
        **kwargs,
    ):
        self.base_branch = base_branch
        self.namespaces_include = namespaces_include
        self.namespaces_exclude = namespaces_exclude
        self.kinds_include = kinds_include
        self.kinds_exclude = kinds_exclude
        self.branch_support = branch_support or [BranchSupportType.AWARE]

        super().__init__(*args, **kwargs)

    def _get_node_where_clause(self, node_variable_name: str) -> str:
        where_clause_parts = []
        where_clause_parts.append(
            f"($namespaces_include IS NULL OR {node_variable_name}.namespace IN $namespaces_include)"
        )
        where_clause_parts.append(
            f"($namespaces_exclude IS NULL OR NOT({node_variable_name}.namespace IN $namespaces_exclude))"
        )
        where_clause_parts.append(f"($kinds_include IS NULL OR {node_variable_name}.kind IN $kinds_include)")
        where_clause_parts.append(f"($kinds_exclude IS NULL OR NOT({node_variable_name}.kind IN $kinds_exclude))")
        where_clause = " AND ".join(where_clause_parts)
        return f"({where_clause})"

    async def query_init(self, db: InfrahubDatabase, **kwargs):
        self.params.update(
            {
                "namespaces_include": self.namespaces_include,
                "namespaces_exclude": self.namespaces_exclude,
                "kinds_include": self.kinds_include,
                "kinds_exclude": self.kinds_exclude,
                "base_branch_name": self.base_branch.name,
                "branch_name": self.branch.name,
                "branch_names": [registry.default_branch, self.branch.name],
                "from_time": self.diff_from.to_string(),
                "to_time": self.diff_to.to_string(),
            }
        )
        p_node_where = self._get_node_where_clause(node_variable_name="p")
        n_node_where = self._get_node_where_clause(node_variable_name="n")

        diff_rel_filter_parts, br_params = self.branch.get_query_filter_range(
            rel_label="diff_rel",
            start_time=self.diff_from,
            end_time=self.diff_to,
        )
        diff_rel_filter = " AND ".join(diff_rel_filter_parts)

        self.params.update(br_params)
        self.params["branch_support"] = [item.value for item in self.branch_support]

        query = """
            // all updated edges
            MATCH (p:Node|Attribute|Relationship)-[diff_rel]->(q)
            WHERE %(diff_rel_filter)s
            AND p.branch_support IN $branch_support
            AND %(p_node_where)s
            // deepest diff edges HAS_VALUE, HAS_SOURCE/OWNER, IS_VISIBLE/PROTECTED
            CALL {
                WITH p, q, diff_rel
                OPTIONAL MATCH path = (
                    (:Root)<-[r_root:IS_PART_OF]-(n:Node)-[r_node:HAS_ATTRIBUTE|IS_RELATED]-(p:Attribute|Relationship)-[diff_rel:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER|HAS_VALUE]->(q:Boolean|Node|AttributeValue)
                )
                WHERE %(n_node_where)s
                AND n <> q
                AND ALL(
                    r in [r_root, r_node]
                    WHERE r.from <= $to_time AND (r.to IS NULL or r.to >= $to_time)
                    AND r.branch IN $branch_names
                )
                WITH path AS diff_rel_path, diff_rel, r_root, n, r_node, p
                ORDER BY
                    r_node.branch = diff_rel.branch DESC,
                    r_root.branch = diff_rel.branch DESC,
                    r_node.from DESC,
                    r_root.from DESC
                LIMIT 1
                // get base branch version of the diff path, if it exists
                WITH diff_rel_path, diff_rel, r_root, n, r_node, p
                OPTIONAL MATCH latest_base_path = (:Root)<-[r_root]-(n)-[r_node]-(p)-[base_diff_rel]->(base_prop)
                WHERE any(r in relationships(diff_rel_path) WHERE r.branch = $branch_name)
                AND n <> base_prop
                AND type(base_diff_rel) = type(diff_rel)
                AND all(
                    r in relationships(latest_base_path)
                    WHERE r.branch = $base_branch_name
                    AND r.from <= $from_time AND (r.to IS NULL or r.to <= $from_time)
                )
                WITH diff_rel_path, latest_base_path, diff_rel, r_root, n, r_node, p
                ORDER BY base_diff_rel.from DESC, r_node.from DESC, r_root.from DESC
                LIMIT 1
                WITH diff_rel_path, latest_base_path, diff_rel, r_root, n, r_node, p
                OPTIONAL MATCH base_peer_path = (
                   (:Root)<-[r_root]-(n)-[r_node]-(p:Relationship)-[base_r_peer:IS_RELATED]-(base_peer:Node)
                )
                WHERE type(diff_rel) <> "IS_RELATED"
                AND base_peer <> n
                AND base_r_peer.from <= $from_time
                AND base_r_peer.branch IN $branch_names
                WITH diff_rel_path, latest_base_path, base_peer_path, base_r_peer, diff_rel
                ORDER BY base_r_peer.branch = diff_rel.branch DESC, base_r_peer.from DESC
                LIMIT 1
                RETURN reduce(
                    diff_rel_paths = [], item IN [diff_rel_path, latest_base_path, base_peer_path] |
                    CASE WHEN item IS NULL THEN diff_rel_paths ELSE diff_rel_paths + [item] END
                ) AS diff_rel_paths
            }
            // middle-level edges, HAS_ATTRIBUTE, IS_RELATED
            WITH p, q, diff_rel, diff_rel_paths AS full_diff_paths
            CALL {
                WITH p, q, diff_rel
                OPTIONAL MATCH path = (
                    (:Root)<-[r_root:IS_PART_OF]-(p:Node)-[diff_rel:HAS_ATTRIBUTE|IS_RELATED]-(q:Attribute|Relationship)-[r_prop:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER|HAS_VALUE|IS_RELATED]-(prop:Boolean|Node|AttributeValue)
                )
                WHERE ALL(
                    r in [r_root, r_prop]
                    WHERE r.from <= $to_time AND (r.to IS NULL or r.to >= $to_time)
                    AND r.branch IN $branch_names
                )
                AND p <> prop
                WITH path, q, prop, r_prop, r_root
                ORDER BY
                    q,
                    prop,
                    r_prop.branch = diff_rel.branch DESC,
                    r_root.branch = diff_rel.branch DESC,
                    r_prop.from DESC,
                    r_root.from DESC
                WITH q, prop, head(collect(path)) AS latest_path
                RETURN latest_path
            }
            WITH p, q, diff_rel, full_diff_paths, collect(latest_path) AS latest_paths
            WITH p, q, diff_rel, full_diff_paths + latest_paths AS full_diff_paths
            // whole node-paths - IS_PART_OF
            CALL {
                WITH p, q, diff_rel
                OPTIONAL MATCH path = (
                    (q:Root)<-[diff_rel:IS_PART_OF]-(p:Node)-[r_node:HAS_ATTRIBUTE|IS_RELATED]-(node:Attribute|Relationship)-[r_prop:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER|HAS_VALUE|IS_RELATED]-(prop:Boolean|Node|AttributeValue)
                )
                WHERE ALL(
                    r in [r_node, r_prop]
                    WHERE r.from <= $to_time AND (r.to IS NULL or r.to >= $to_time)
                    AND r.branch IN $branch_names
                )
                AND p <> prop
                WITH path, node, prop, r_prop, r_node
                ORDER BY
                    node,
                    prop,
                    r_prop.branch = diff_rel.branch DESC,
                    r_node.branch = diff_rel.branch DESC,
                    r_prop.from DESC,
                    r_node.from DESC
                WITH node, prop, head(collect(path)) AS latest_path
                RETURN latest_path
            }
            WITH p, q, diff_rel, full_diff_paths, collect(latest_path) AS latest_paths
            WITH p, q, diff_rel, full_diff_paths + latest_paths AS full_diff_paths
        """ % {
            "diff_rel_filter": diff_rel_filter,
            "p_node_where": p_node_where,
            "n_node_where": n_node_where,
        }

        self.add_to_query(query)
        self.return_labels = ["diff_rel", "full_diff_paths"]
