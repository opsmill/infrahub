from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional

import pendulum
from pydantic import validator

import infrahub.config as config
from infrahub.core.attribute.query import AttributeGetValueQuery
from infrahub.core.constants import RelationshipStatus
from infrahub.core.node.standard import StandardNode
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import (
    add_relationship,
    update_relationships_to,
)
from infrahub.database import execute_read_query
from infrahub.exceptions import BranchNotFound


class DiffQuery(Query):
    pass


class AddNodeToBranch(Query):

    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, node_id, *args, **kwargs):

        self.node_id = node_id
        super().__init__(*args, **kwargs)

    def query_init(self):
        query = """
        MATCH (b:Branch { name: $branch })
        MATCH (d) WHERE ID(d) = $node_id
        WITH b,d
        CREATE (d)-[r:IS_PART_OF { from: $now, to: null, status: $status }]->(b)
        RETURN ID(r)
        """

        self.params["node_id"] = self.node_id
        self.params["now"] = self.at or pendulum.now(tz="UTC").to_iso8601_string()
        self.params["branch"] = self.branch.name
        self.params["status"] = RelationshipStatus.ACTIVE.value

        self.add_to_query(query)
        # results = execute_write_query(create_rel_query, params)
        # if not results:
        #     return None
        # return results[0].values()[0]


class Branch(StandardNode):
    name: str
    status: str = "OPEN"  # OPEN, CLOSED
    description: Optional[str]
    origin_branch: str = "main"
    branched_from: Optional[str]
    is_default: bool = False
    is_protected: bool = False
    is_data_only: bool = False

    ephemeral_rebase: bool = False

    _exclude_attrs: List[str] = ["id", "uuid", "owner", "ephemeral_rebase"]

    @validator("branched_from", pre=True, always=True)
    def set_branched_from(cls, value):
        return value or pendulum.now(tz="UTC").to_iso8601_string()

    @classmethod
    def get_by_name(cls, name):

        query = """
        MATCH (n:Branch)
        WHERE n.name = $name
        RETURN n
        """

        params = {"name": name}

        results = execute_read_query(query, params)

        if len(results) == 0:
            raise BranchNotFound(identifier=name)

        return cls._convert_node_to_obj(results[0].values()[0])

    def get_branches_and_times_to_query(self, at=None):

        default_branch = config.SETTINGS.main.default_branch

        if self.name == default_branch:
            return {default_branch: at or "current()"}

        time_default_branch = self.branched_from
        # If we are querying before the beginning of the branch
        # the time for the main branhc must be the time of the query
        if at and (self.ephemeral_rebase or pendulum.parse(at) < pendulum.parse(time_default_branch)):
            time_default_branch = at
        elif self.ephemeral_rebase and not at:
            time_default_branch = "current()"

        return {
            default_branch: time_default_branch,
            self.name: at or "current()",
        }

    def get_query_filter_branch_to_node(
        self, rel_label="r", branch_label="b", at=None, include_outside_parentheses=False
    ):

        filters = []
        params = {}

        for idx, (branch_name, time_to_query) in enumerate(self.get_branches_and_times_to_query(at=at).items()):

            br_filter = f"({branch_label}.name = $branch{idx} AND ("
            br_filter += f"({rel_label}.from <= $time{idx} AND {rel_label}.to IS NULL)"
            br_filter += f" OR ({rel_label}.from <= $time{idx} AND {rel_label}.to >= $time{idx})"
            br_filter += "))"

            filters.append(br_filter)
            params[f"branch{idx}"] = branch_name
            params[f"time{idx}"] = time_to_query

        if not include_outside_parentheses:
            return "\n OR ".join(filters), params

        return "(" + "\n OR ".join(filters) + ")", params

    def get_query_filter_relationships(self, rel_labels: list, at=None, include_outside_parentheses=False):

        filters = []
        params = {}

        # TODO add a check to ensure rel_labels is a list
        #   automatically convert to a list of one if needed

        branches_times = self.get_branches_and_times_to_query(at=at)

        for idx, (branch_name, time_to_query) in enumerate(branches_times.items()):
            params[f"branch{idx}"] = branch_name
            params[f"time{idx}"] = time_to_query

        for rel in rel_labels:

            filters_per_rel = []
            for idx, (branch_name, time_to_query) in enumerate(branches_times.items()):

                filters_per_rel.append(
                    f"({rel}.branch = $branch{idx} AND {rel}.from <= $time{idx} AND {rel}.to IS NULL)"
                )
                filters_per_rel.append(
                    f"({rel}.branch = $branch{idx} AND {rel}.from <= $time{idx} AND {rel}.to >= $time{idx})"
                )

            if not include_outside_parentheses:
                filters.append("\n OR ".join(filters_per_rel))

            filters.append("(" + "\n OR ".join(filters_per_rel) + ")")

        return filters, params

    def rebase(self):
        """Rebase the current Branch with its origin branch"""

        self.branched_from = pendulum.now(tz="UTC").to_iso8601_string()
        self.save()

        # Update the branch in the registry after the rebase
        from infrahub.core import registry

        registry.branch[self.name] = self

    def validate(self):
        """Validate if a branch is eligible to be merged.
        - Must be conflict free both for data and repository
        - All checks must pass
        - Check schema changes

        Need to support with and without rebase

        Need to return a list of violations, must be multiple
        """

        passed = True
        messages = []

        from infrahub.core.manager import NodeManager

        # For all repositories in this branch, run all checks
        repos = NodeManager.query("Repository", branch=self)
        for repo in repos:
            result, errors = repo.run_checks()
            if not result:
                messages.extend(errors)
                passed = False

        return passed, messages

    def diff(self):
        return Diff(branch=self)

    def merge(self):
        """Merge the current branch into main."""

        passed, messages = self.validate()
        if not passed:
            raise Exception(f"Unable to merge branch {self.name}, validation failed")

        from infrahub.core import registry

        node_uuid_already_merged = []
        rel_ids_to_update = []

        default_branch = registry.branch[config.SETTINGS.main.default_branch]

        at = Timestamp()

        # ---------------------------------------------
        # NODES
        #  To access the internal value of this relationship, we need to re-query the list of nodes
        # ---------------------------------------------
        query = DiffNodeQuery(branch=self)
        query.execute()

        for result in query.get_results():

            # For now only consider the item that have been changed in the branch
            if result.get("b").get("name") != self.name:
                continue

            if result.get("n").get("uuid") not in node_uuid_already_merged:
                node_uuid_already_merged.append(result.get("n").get("uuid"))
                add_query = AddNodeToBranch(node_id=result.get("n").id, branch=default_branch)
                add_query.execute()
                rel_ids_to_update.append(result.get("r1").id)

            # Create relationship
            add_relationship(result.get("n"), result.get("a"), "HAS_ATTRIBUTE")
            add_relationship(result.get("a"), result.get("av"), "HAS_VALUE")
            rel_ids_to_update.append(result.get("r2").id)
            rel_ids_to_update.append(result.get("r3").id)

        # ---------------------------------------------
        # ATTRIBUTES
        # ---------------------------------------------
        query = DiffAttributeQuery(branch=self)
        query.execute()

        for result in query.get_results_group_by_branch_attribute():

            # Ignore attributes that are associated with a new node
            if result.get("n").get("uuid") in node_uuid_already_merged:
                continue

            # For now only consider the item that have been changed in the branch
            if result.get("r").get("branch") != self.name:
                continue

            # Need to find the current valid relationship in main and update its time
            previous_value_query = AttributeGetValueQuery(
                attr_id=result.get("a").id, branch=default_branch, at=at
            ).execute()
            previous_value_result = previous_value_query.get_result()

            add_relationship(result.get("a"), result.get("av"), "HAS_VALUE")
            rel_ids_to_update.append(result.get("r").id)
            rel_ids_to_update.append(previous_value_result.get("r").id)

        # ---------------------------------------------
        # RELATIONSHIPS
        # ---------------------------------------------
        query = DiffRelationshipQuery(branch=self)
        query.execute()

        for result in query.get_results_deduplicated():

            # For now only consider the item that have been changed in the branch
            if result.get("r1").get("branch") != self.name:
                continue

            add_relationship(result.get("sn"), result.get("rel"), result.get("r1").type)
            add_relationship(result.get("dn"), result.get("rel"), result.get("r2").type)
            rel_ids_to_update.append(result.get("r1").id)
            rel_ids_to_update.append(result.get("r2").id)

        update_relationships_to(ids=rel_ids_to_update)

        # ---------------------------------------------
        # FILES
        # ---------------------------------------------

        # FIXME Need to redefine with new repository model
        # # Collect all Repositories in Main because we'll need the commit in Main for each one.
        # repos_in_main = {repo.uuid: repo for repo in Repository.get_list()}

        # for repo in Repository.get_list(branch=self):

        #     # Check if the repo, exist in main, if not ignore this repo
        #     if repo.uuid not in repos_in_main:
        #         continue

        #     repo_in_main = repos_in_main[repo.uuid]
        #     changed_files = repo.calculate_diff_with_commit(repo_in_main.commit.value)

        #     if not changed_files:
        #         continue

        #     repo.merge()

        self.rebase()


class DiffNodeQuery(DiffQuery):
    def query_init(self):

        # TODO need to improve the query to capture an object that has been delete into the branch
        # TODO probably also need to consider a node what was merged already
        query = """
        MATCH (b:Branch { name: $branch })-[r1:IS_PART_OF]-(n)-[r2:HAS_ATTRIBUTE]-(a:Attribute)-[r3:HAS_VALUE]-(av)
        """

        self.add_to_query(query)
        self.params["branch"] = self.branch.name
        self.params["time0"] = self.branch.branched_from

        self.order_by = ["n.uuid"]

        self.return_labels = ["b", "n", "a", "av", "r1", "r2", "r3"]


class DiffAttributeQuery(DiffQuery):
    def query_init(self):

        # TODO need to improve the query to capture an object that has been delete into the branch
        query = """
        MATCH (n)-[:HAS_ATTRIBUTE]-(a:Attribute)-[r { branch: $branch_name } ]->(av)
        WHERE (r.from > $time0 ) OR (r.to < $time0 )
        """

        self.add_to_query(query)
        self.params["branch_name"] = self.branch.name
        self.params["time0"] = self.branch.branched_from

        self.return_labels = ["n", "a", "av", "r"]

    def get_results_group_by_branch_attribute(self):  # -> Generator[QueryResult]:
        """Return results group by the label and attribute provided and filtered by scored."""

        attrs_info = defaultdict(list)

        # Extract all attrname and relationships on all branches
        for idx, result in enumerate(self.results):
            node_uuid = result.get("n").get("uuid")
            attribute_name = result.get("a").get("name", None)
            attribute_branch = result.get("r").get("branch")

            attr_key = f"{node_uuid}__{attribute_branch}__{attribute_name}"
            info = {"idx": idx, "branch_score": result.branch_score}
            attrs_info[attr_key].append(info)

        for attr_key, values in attrs_info.items():
            attr_info = sorted(values, key=lambda i: i["branch_score"], reverse=True)[0]

            yield self.results[attr_info["idx"]]


class DiffRelationshipQuery(DiffQuery):
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


# For now a diff is always calculated between a given branch and the main branch
#   need to search for
#      relationships that are referencing the new branch
#      relationships in main that have changed between the branched_from date and the current time


@dataclass
class NodeAttributeDiffElement:
    attr_uuid: str
    attr_name: str
    action: str
    changed_at: str


@dataclass
class NodeDiffElement:
    branch: str
    node_labels: List[str]
    node_uuid: str
    action: str
    changed_at: str
    attributes: List[NodeAttributeDiffElement]


@dataclass
class AttributeDiffElement:
    branch: str
    node_labels: List[str]
    node_uuid: str
    attr_uuid: str
    attr_name: str
    action: str
    changed_at: str


@dataclass
class RelationshipDiffElement:
    branch: str
    source_node_labels: List[str]
    source_node_uuid: str
    dest_node_labels: List[str]
    dest_node_uuid: str
    rel_uuid: str
    rel_name: str
    action: str
    changed_at: str


class Diff:
    def __init__(self, branch):
        self.branch = branch

        # internal cache to avoir re-querying everything
        self._nodes = None

    def get_nodes(self, use_cache=True) -> List[NodeDiffElement]:

        if self._nodes and use_cache:
            return self._nodes

        query = DiffNodeQuery(branch=self.branch)
        query.execute()
        results = []

        node = None
        for result in query.get_results():

            # Determine if we need to create a new node
            # Before creating a new one we need to save the previous one to the list of result
            created_new_node = False # noqa
            if not node or node.node_uuid != result.get("n").get("uuid"):
                created_new_node = True # noqa  
                if node:
                    results.append(node)

                item = {
                    "branch": result.get("b").get("name"),
                    "node_labels": list(result.get("n").labels),
                    "node_uuid": result.get("n").get("uuid"),
                    "attributes": [],
                }

                from_time = result.get("r1").get("from")
                to_time = result.get("r1").get("to")

                if from_time and not to_time:
                    item["changed_at"] = from_time
                    item["action"] = "added"

                elif from_time and to_time:
                    item["changed_at"] = to_time
                    item["action"] = "removed"

                node = NodeDiffElement(**item)

            node.attributes.append(
                NodeAttributeDiffElement(
                    attr_uuid=result.get("a").get("uuid"),
                    attr_name=result.get("a").get("name"),
                    changed_at=result.get("r2").get("from"),
                    action="added",
                )
            )

        if node:
            results.append(node)

        self._nodes = results

        return results

    def get_attributes(self):

        # TODO Currently only the attribute updated in the branch will be returned
        # Need to also query the attribute that have been added/updated/deleted in main after the checkout time
        query = DiffAttributeQuery(branch=self.branch)
        query.execute()
        results = []

        node_ids = [node.node_uuid for node in self.get_nodes()]

        for result in query.get_results_group_by_branch_attribute():

            # Ignore attributes that are associated with a new node
            if result.get("n").get("uuid") in node_ids:
                continue

            item = AttributeDiffElement(
                branch=result.get("r").get("branch"),
                node_labels=list(result.get("n").labels),
                node_uuid=result.get("n").get("uuid"),
                attr_name=result.get("a").get("name"),
                attr_uuid=result.get("a").get("uuid"),
                changed_at=result.get("r").get("from"),
                action="updated",
            )

            results.append(item)

        return results

    def get_relationships(self):

        results = []

        query = DiffRelationshipQuery(branch=self.branch)
        query.execute()

        for result in query.get_results_deduplicated():

            item = RelationshipDiffElement(
                branch=result.get("r1").get("branch"),
                source_node_labels=list(result.get("sn").labels),
                source_node_uuid=result.get("sn").get("uuid"),
                dest_node_labels=list(result.get("dn").labels),
                dest_node_uuid=result.get("dn").get("uuid"),
                rel_uuid=result.get("rel").get("uuid"),
                rel_name=result.get("rel").get("name"),
                changed_at=result.get("r1").get("from"),
                action="added",
            )
            results.append(item)

        return results

    def get_files(self):

        results = []

        # FIXME Need to revisit with new repository model

        # # Collect all Repositories in Main because we'll need the commit in Main for each one.
        # repos_in_main = {repo.uuid: repo for repo in Repository.get_list()}

        # for repo in Repository.get_list(branch=self.branch):

        #     # Check if the repo, exist in main, if not ignore this repo
        #     if repo.uuid not in repos_in_main:
        #         continue

        #     repo_in_main = repos_in_main[repo.uuid]
        #     changed_files = repo.calculate_diff_with_commit(repo_in_main.commit.value)

        #     if not changed_files:
        #         continue

        #     results.append(
        #         {
        #             "branch": repo.branch.name,
        #             "repository_uuid": repo.uuid,
        #             "repository_name": repo.name.value,
        #             "files": changed_files,
        #         }
        #     )

        return results
