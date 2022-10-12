from __future__ import annotations

from collections import defaultdict
from typing import Generator, List

from infrahub.core.query import Query, QueryType, QueryResult
from infrahub.core.timestamp import Timestamp


class DiffQuery(Query):

    branch_names: List[str]
    diff_from: Timestamp
    diff_to: Timestamp

    def __init__(self, branch, diff_from=None, diff_to=None, *args, **kwargs):
        """A diff is always in the context of a branch"""

        if diff_from:
            self.diff_from = Timestamp(diff_from)
        elif not diff_from and not branch.is_default:
            self.diff_from = Timestamp(branch.branched_from)
        else:
            raise ValueError("diff_from is mandatory with the diff is on the main branch.")

        # If Diff_to is not defined it will automatically select the current time.
        self.diff_to = Timestamp(diff_to)

        if self.diff_to < self.diff_from:
            raise ValueError("diff_to must be later than diff_from")

        if branch.is_default:
            self.branch_names = [branch.name]
        else:
            self.branch_names = [branch.name, branch.origin_branch]

        super().__init__(branch, *args, **kwargs)


class DiffNodeQuery(DiffQuery):

    name: str = "diff_node"
    type: QueryType = QueryType.READ

    def query_init(self):

        # TODO need to improve the query to capture an object that has been delete into the branch
        # TODO probably also need to consider a node what was merged already
        query = """
        MATCH (b:Branch)-[r:IS_PART_OF]-(n)
        WHERE (b.name in $branch_names AND r.from >= $from ) OR (b.name in $branch_names AND r.to <= $from)
        """

        self.add_to_query(query)
        self.params["branch_names"] = self.branch_names
        self.params["from"] = self.diff_from.to_string()

        self.order_by = ["n.uuid"]

        self.return_labels = ["b", "n", "r"]


class DiffAttributeQuery(DiffQuery):

    name: str = "diff_attribute"
    type: QueryType = QueryType.READ

    def query_init(self):

        # TODO need to improve the query to capture an object that has been deleted into the branch
        query = """
        MATCH (n)-[r1:HAS_ATTRIBUTE]-(a:Attribute)-[r2:HAS_VALUE|IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]->(ap)
        WHERE (r2.branch IN $branch_names AND r2.from >= $from ) OR (r2.branch IN $branch_names AND r2.to <= $from)
        """

        self.add_to_query(query)
        self.params["branch_names"] = self.branch_names
        self.params["from"] = self.diff_from.to_string()

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

    def query_init(self):

        query = """
        MATCH (sn)-[r1 { branch: $branch_name }]->(rel:Relationship)<-[r2 { branch: $branch_name } ]->(dn)
        """

        self.add_to_query(query)
        self.params["branch_name"] = self.branch.name
        self.params["time0"] = self.branch.branched_from

        self.return_labels = ["sn", "dn", "rel", "r1", "r2"]

    def get_results_deduplicated(self):

        attrs_info = defaultdict(list)
        ids_set_processed = []

        # Extract all attrname and relationships on all branches
        for idx, result in enumerate(self.results):

            # Generate unique set composed of all the IDs of th node and the relationship returned
            # To identify the duplicate of the query and remove it. (same path traversed from the other direction)
            ids_set = set([item.id for item in result])
            if ids_set in ids_set_processed:
                continue
            ids_set_processed.append(ids_set)

            # Generate a unique KEY that will be the same irrespectively of the order used to traverse the relationship
            source_node_uuid = result.get("sn").get("uuid")[8:]
            dest_node_uuid = result.get("dn").get("uuid")[8:]
            nodes = sorted([source_node_uuid, dest_node_uuid])
            rel_name = result.get("rel").get("name")

            attr_key = f"{nodes[0]}__{nodes[1]}__{rel_name}"
            info = {"idx": idx, "branch_score": result.branch_score}
            attrs_info[attr_key].append(info)

        for attr_key, values in attrs_info.items():
            attr_info = sorted(values, key=lambda i: i["branch_score"], reverse=True)[0]

            yield self.results[attr_info["idx"]]
