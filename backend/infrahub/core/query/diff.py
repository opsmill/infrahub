from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Union

from infrahub.core.constants import BranchSupportType
from infrahub.core.query import Query, QueryResult, QueryType, sort_results_by_time
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class DiffQuery(Query):
    branch_names: List[str]
    diff_from: Timestamp
    diff_to: Timestamp
    type: QueryType = QueryType.READ

    def __init__(
        self,
        branch: Branch,
        diff_from: Union[Timestamp, str] = None,
        diff_to: Union[Timestamp, str] = None,
        *args,
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

        super().__init__(branch, *args, **kwargs)


class DiffNodeQuery(DiffQuery):
    name: str = "diff_node"

    def __init__(
        self,
        namespaces_include: Optional[List[str]] = None,
        namespaces_exclude: Optional[List[str]] = None,
        kinds_include: Optional[List[str]] = None,
        kinds_exclude: Optional[List[str]] = None,
        branch_support: Optional[List[BranchSupportType]] = None,
        *args,
        **kwargs,
    ):
        self.namespaces_include = namespaces_include
        self.namespaces_exclude = namespaces_exclude
        self.kinds_include = kinds_include
        self.kinds_exclude = kinds_exclude
        self.branch_support = branch_support or [BranchSupportType.AWARE]

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
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
        namespaces_include: Optional[List[str]] = None,
        namespaces_exclude: Optional[List[str]] = None,
        kinds_include: Optional[List[str]] = None,
        kinds_exclude: Optional[List[str]] = None,
        branch_support: Optional[List[BranchSupportType]] = None,
        *args,
        **kwargs,
    ):
        self.namespaces_include = namespaces_include
        self.namespaces_exclude = namespaces_exclude
        self.kinds_include = kinds_include
        self.kinds_exclude = kinds_exclude
        self.branch_support = branch_support or [BranchSupportType.AWARE]

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
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
        namespaces_include: Optional[List[str]] = None,
        namespaces_exclude: Optional[List[str]] = None,
        kinds_include: Optional[List[str]] = None,
        kinds_exclude: Optional[List[str]] = None,
        branch_support: Optional[List[BranchSupportType]] = None,
        *args,
        **kwargs,
    ):
        self.namespaces_include = namespaces_include
        self.namespaces_exclude = namespaces_exclude
        self.kinds_include = kinds_include
        self.kinds_exclude = kinds_exclude
        self.branch_support = branch_support or [BranchSupportType.AWARE]

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
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

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
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

    def __init__(
        self,
        ids: List[str],
        diff_from: str,
        diff_to: str,
        account=None,
        *args,
        **kwargs,
    ):
        self.account = account
        self.ids = ids
        self.time_from = Timestamp(diff_from)
        self.time_to = Timestamp(diff_to)

        super().__init__(order_by=["a.name"], *args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
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

    def get_results_by_id_and_prop_type(self, attr_id: str, prop_type: str) -> List[QueryResult]:
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
    order_by: List[str] = ["a.name"]

    def __init__(
        self,
        ids: List[str],
        at: str,
        account=None,
        *args,
        **kwargs,
    ):
        self.account = account
        self.ids = ids
        self.at = Timestamp(at)

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.params["ids"] = self.ids

        rels_filter, rels_params = self.branch.get_query_filter_relationships(
            rel_labels=["r"], at=self.at, include_outside_parentheses=True
        )

        self.params.update(rels_params)

        query = """
        MATCH (a) WHERE a.uuid IN $ids
        MATCH (a)-[r:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER|HAS_VALUE]-(ap)
        WHERE %s
        """ % ("\n AND ".join(rels_filter),)

        self.add_to_query(query)
        self.return_labels = ["a", "ap", "r"]

    def get_results_by_id_and_prop_type(self, attr_id: str, prop_type: str) -> List[QueryResult]:
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
        ids: List[str],
        diff_from: str,
        diff_to: str,
        account=None,
        *args,
        **kwargs,
    ):
        self.account = account
        self.ids = ids
        self.time_from = Timestamp(diff_from)
        self.time_to = Timestamp(diff_to)

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.params["ids"] = self.ids

        rels_filter, rels_params = self.branch.get_query_filter_relationships_range(
            rel_labels=["r"], start_time=self.time_from, end_time=self.time_to, include_outside_parentheses=True
        )

        self.params.update(rels_params)

        # TODO Compute the list of potential relationship dynamically in the future based on the class
        query = """
        MATCH (rl) WHERE rl.uuid IN $ids
        MATCH (rl)-[r:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]-(rp)
        WHERE %s
        """ % ("\n AND ".join(rels_filter),)

        self.params["at"] = self.at.to_string()

        self.add_to_query(query)
        self.return_labels = ["rl", "rp", "r"]

    def get_results_by_id_and_prop_type(self, rel_id: str, prop_type: str) -> List[QueryResult]:
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
