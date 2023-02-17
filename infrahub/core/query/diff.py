from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Generator, List, Union

from infrahub.core.query import Query, QueryResult, QueryType, sort_results_by_time
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch


class DiffQuery(Query):
    branch_names: List[str]
    diff_from: Timestamp
    diff_to: Timestamp

    def __init__(
        self,
        branch: Branch,
        diff_from: Union[Timestamp, str] = None,
        diff_to: Union[Timestamp, str] = None,
        *args,
        **kwargs,
    ):
        """A diff is always in the context of a branch"""

        if diff_from:
            self.diff_from = Timestamp(diff_from)
        elif not diff_from and not branch.is_default:
            self.diff_from = Timestamp(branch.branched_from)
        else:
            raise ValueError("diff_from is mandatory when the diff is on the main branch.")

        # If Diff_to is not defined it will automatically select the current time.
        self.diff_to = Timestamp(diff_to)

        if self.diff_to < self.diff_from:
            raise ValueError("diff_to must be later than diff_from")

        self.branch_names = branch.get_branches_in_scope()

        super().__init__(branch, *args, **kwargs)


class DiffNodeQuery(DiffQuery):
    name: str = "diff_node"
    type: QueryType = QueryType.READ

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        # TODO need to improve the query to capture an object that has been delete into the branch
        # TODO probably also need to consider a node what was merged already

        br_filter, br_params = self.branch.get_query_filter_branch_range(
            branch_label="b",
            rel_label="r",
            start_time=self.diff_from,
            end_time=self.diff_to,
        )

        self.params.update(br_params)

        query = """
        MATCH (b:Branch)-[r:IS_PART_OF]-(n)
        WHERE %s
        """ % (
            "\n AND ".join(br_filter),
        )

        self.add_to_query(query)
        self.order_by = ["n.uuid"]

        self.return_labels = ["b", "n", "r"]


class DiffAttributeQuery(DiffQuery):
    name: str = "diff_attribute"
    type: QueryType = QueryType.READ

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        # TODO need to improve the query to capture an object that has been deleted into the branch
        query = """
        MATCH (n)-[r1:HAS_ATTRIBUTE]-(a:Attribute)-[r2:HAS_VALUE|IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]->(ap)
        WHERE (r2.branch IN $branch_names AND r2.from >= $from AND r2.from <= $to ) OR (r2.branch IN $branch_names AND r2.from >= $from AND r2.to <= $from)
        """

        self.add_to_query(query)
        self.params["branch_names"] = self.branch_names
        self.params["from"] = self.diff_from.to_string()
        self.params["to"] = self.diff_to.to_string()

        self.return_labels = ["n", "a", "ap", "r1", "r2"]

    def get_results_group_by_branch_attribute(self) -> Generator[QueryResult, None, None]:
        """Return results grouped by the label and attribute provided and filtered by scored."""

        attrs_info = defaultdict(list)

        # Extract all attrname and relationships on all branches
        for idx, result in enumerate(self.results):
            node_uuid = result.get("n").get("uuid")
            attribute_name = result.get("a").get("name", None)
            attribute_branch = result.get("r2").get("branch")
            property_type = result.get("r2").type.lower()

            attr_key = f"{node_uuid}__{attribute_branch}__{attribute_name}__{property_type}"
            info = {"idx": idx, "branch_score": result.branch_score}
            attrs_info[attr_key].append(info)

        for attr_key, values in attrs_info.items():
            attr_info = sorted(values, key=lambda i: i["branch_score"], reverse=True)[0]

            yield self.results[attr_info["idx"]]


class DiffRelationshipQuery(DiffQuery):
    name: str = "diff_relationship"
    type: QueryType = QueryType.READ

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        query = """
        MATCH p = ((sn)-[r1]->(rel:Relationship)<-[r2]-(dn))
        WHERE (r1.branch = r2.branch AND (r1.to = r2.to OR (r1.to is NULL AND r2.to is NULL)) AND r1.from = r2.from AND r1.status = r2.status
          AND all(r IN relationships(p) WHERE (r.branch IN $branch_names AND r.from >= $diff_from AND r.from <= $diff_to AND ((r.to >= $diff_from AND r.to <= $diff_to) OR r.to is NULL))))
        """

        self.add_to_query(query)
        self.params["branch_names"] = self.branch_names
        self.params["diff_from"] = self.diff_from.to_string()
        self.params["diff_to"] = self.diff_to.to_string()

        self.return_labels = ["sn", "dn", "rel", "r1", "r2"]

    def get_results(self) -> Generator[QueryResult, None, None]:
        if not self.results:
            return iter(())

        attrs_info = defaultdict(list)
        ids_set_processed = []

        # Extract all attrname and relationships on all branches
        for idx, result in enumerate(self.results):
            # Generate unique set composed of all the IDs of the nodes and the relationship returned
            # To identify the duplicate of the query and remove it. (same path traversed from the other direction)
            ids_set = {item.element_id for item in result}
            if ids_set in ids_set_processed:
                continue
            ids_set_processed.append(ids_set)

            # Generate a unique KEY that will be the same irrespectively of the order used to traverse the relationship
            source_node_uuid = result.get("sn").get("uuid")[8:]
            dest_node_uuid = result.get("dn").get("uuid")[8:]
            nodes = sorted([source_node_uuid, dest_node_uuid])
            rel_name = result.get("rel").get("name")
            branch_name = result.get("r1").get("branch")

            attr_key = f"{branch_name}_{nodes[0]}__{nodes[1]}__{rel_name}"
            info = {"idx": idx, "branch_score": result.branch_score}
            attrs_info[attr_key].append(info)

        for attr_key, values in attrs_info.items():
            attr_info = sorted(values, key=lambda i: i["branch_score"], reverse=True)[0]

            yield self.results[attr_info["idx"]]

        return iter(())


class DiffRelationshipPropertyQuery(DiffQuery):
    name: str = "diff_relationship_property"
    type: QueryType = QueryType.READ

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        rels_filter, rels_params = self.branch.get_query_filter_path(at=self.diff_to)
        self.params.update(rels_params)

        query = (
            """
        MATCH (rel:Relationship)-[r3:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]-(rp)
        WHERE (r3.branch IN $branch_names AND r3.from >= $diff_from AND r3.from <= $diff_to AND ((r3.to >= $diff_from AND r3.to <= $diff_to) OR r3.to is NULL))
        WITH *
        MATCH p = ((sn)-[r1]->(rel)<-[r2]-(dn))
        WHERE r1.branch = r2.branch AND (r1.to = r2.to OR (r1.to is NULL AND r2.to is NULL)) AND r1.from = r2.from AND r1.status = r2.status AND all(r IN relationships(p) WHERE ( %s ))
        """
            % rels_filter
        )

        self.add_to_query(query)
        self.params["branch_names"] = self.branch_names
        self.params["diff_from"] = self.diff_from.to_string()
        self.params["diff_to"] = self.diff_to.to_string()

        self.return_labels = ["sn", "dn", "rel", "rp", "r3", "r1", "r2"]

    # FIXME, refactor this function to
    #   1/ avoid dup code with DiffRelationshipPropertyQuery
    #   2/ leverage the code from Group_by
    def get_results(self) -> Generator[QueryResult, None, None]:
        if not self.results:
            return iter(())

        attrs_info = defaultdict(list)
        ids_set_processed = []

        # Extract all attrname and relationships on all branches
        for idx, result in enumerate(self.results):
            # Generate unique set composed of all the IDs of the nodes and the relationship returned
            # To identify the duplicate of the query and remove it. (same path traversed from the other direction)
            ids_set = {item.element_id for item in result}
            if ids_set in ids_set_processed:
                continue
            ids_set_processed.append(ids_set)

            # Generate a unique KEY that will be the same irrespectively of the order used to traverse the relationship
            source_node_uuid = result.get("sn").get("uuid")[8:]
            dest_node_uuid = result.get("dn").get("uuid")[8:]
            prop_type = result.get("r3").type
            nodes = sorted([source_node_uuid, dest_node_uuid])
            rel_name = result.get("rel").get("name")
            branch_name = result.get("r1").get("branch")

            attr_key = f"{branch_name}_{nodes[0]}__{nodes[1]}__{rel_name}__{prop_type}"
            info = {"idx": idx, "branch_score": result.branch_score}
            attrs_info[attr_key].append(info)

        for attr_key, values in attrs_info.items():
            attr_info = sorted(values, key=lambda i: i["branch_score"], reverse=True)[0]

            yield self.results[attr_info["idx"]]

        return iter(())


class DiffNodePropertiesByIDSRangeQuery(Query):
    name: str = "diff_node_properties_range_ids"
    order_by: List[str] = ["a.name"]

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

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        self.params["ids"] = self.ids

        rels_filter, rels_params = self.branch.get_query_filter_relationships_range(
            rel_labels=["r"], start_time=self.time_from, end_time=self.time_to, include_outside_parentheses=True
        )

        self.params.update(rels_params)

        query = """
        MATCH (a) WHERE a.uuid IN $ids
        MATCH (a)-[r:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER|HAS_VALUE]-(ap)
        WHERE %s
        """ % (
            "\n AND ".join(rels_filter),
        )

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

    async def query_init(self, session: AsyncSession, *args, **kwargs):
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
        """ % (
            "\n AND ".join(rels_filter),
        )

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


# class DiffNodePropertiesByIDSRangeQuery(Query):
#     name = "diff_node_properties_range_ids"
