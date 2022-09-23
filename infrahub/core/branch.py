from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Set, Union, Optional, Generator

from pydantic import validator

import infrahub.config as config
from infrahub.core.constants import RelationshipStatus
from infrahub.core.query import Query, QueryType
from infrahub.core.query.diff import DiffNodeQuery, DiffAttributeQuery, DiffRelationshipQuery
from infrahub.core.query.attribute import AttributeGetValueQuery
from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.core.node.standard import StandardNode
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import (
    add_relationship,
    update_relationships_to,
)
from infrahub.database import execute_read_query
from infrahub.exceptions import BranchNotFound


class AddNodeToBranch(Query):

    name: str = "node_add_to_branch"
    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, node_id: int, *args, **kwargs):

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
        self.params["now"] = self.at.to_string()
        self.params["branch"] = self.branch.name
        self.params["status"] = RelationshipStatus.ACTIVE.value

        self.add_to_query(query)


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
        return value or Timestamp().to_string()

    @classmethod
    def get_by_name(cls, name: str) -> Branch:

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

    def get_branches_and_times_to_query(self, at: Union[Timestamp, str] = None) -> Dict[str, str]:
        """Get all the branches that are constituing this branch with the associated times."""

        at = Timestamp(at)
        default_branch = config.SETTINGS.main.default_branch

        if self.name == default_branch:
            return {default_branch: at.to_string()}

        time_default_branch = Timestamp(self.branched_from)

        # If we are querying before the beginning of the branch
        # the time for the main branch must be the time of the query
        if self.ephemeral_rebase or at < time_default_branch:
            time_default_branch = at

        return {
            default_branch: time_default_branch.to_string(),
            self.name: at.to_string(),
        }

    def get_query_filter_branch_to_node(
        self,
        rel_label: str = "r",
        branch_label: str = "b",
        at: Union[Timestamp, str] = None,
        include_outside_parentheses: bool = False,
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

    def get_query_filter_relationships(
        self, rel_labels: list, at: Union[Timestamp, str] = None, include_outside_parentheses: bool = False
    ) -> Set[List, Dict]:

        filters = []
        params = {}

        # TODO add a check to ensure rel_labels is a list
        #   automatically convert to a list of one if needed

        at = Timestamp(at)
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

    def get_query_filter_path(self, at: Union[Timestamp, str] = None) -> Set[str, Dict]:

        at = Timestamp(at)
        branches_times = self.get_branches_and_times_to_query(at=at.to_string())

        params = {}
        for idx, (branch_name, time_to_query) in enumerate(branches_times.items()):
            params[f"branch{idx}"] = branch_name
            params[f"time{idx}"] = time_to_query

        filters = []
        for idx, (branch_name, time_to_query) in enumerate(branches_times.items()):

            filters.append(f"(r.branch = $branch{idx} AND r.from <= $time{idx} AND r.to IS NULL)")
            filters.append(f"(r.branch = $branch{idx} AND r.from <= $time{idx} AND r.to >= $time{idx})")

        filter = "(" + "\n OR ".join(filters) + ")"

        return filter, params

    def rebase(self):
        """Rebase the current Branch with its origin branch"""

        self.branched_from = Timestamp().to_string()
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

    def merge(self, at=None):
        """Merge the current branch into main."""

        passed, messages = self.validate()
        if not passed:
            raise Exception(f"Unable to merge branch {self.name}, validation failed")

        from infrahub.core import registry

        node_uuid_already_merged = []
        rel_ids_to_update = []

        default_branch = registry.branch[config.SETTINGS.main.default_branch]

        at = Timestamp(at)

        # ---------------------------------------------
        # NODES
        #  To access the internal value of this relationship, we need to re-query the list of nodes
        # ---------------------------------------------
        query = DiffNodeQuery(branch=self).execute()

        for result in query.get_results():

            # For now only consider the item that have been changed in the branch
            if result.get("b").get("name") != self.name:
                continue

            if result.get("n").get("uuid") not in node_uuid_already_merged:
                node_uuid_already_merged.append(result.get("n").get("uuid"))
                add_query = AddNodeToBranch(node_id=result.get("n").id, branch=default_branch)
                add_query.execute()
                rel_ids_to_update.append(result.get("r1").id)

            # Create Relationships in main
            add_relationship(src_node=result.get("n"), dst_node=result.get("a"), rel_type="HAS_ATTRIBUTE", at=at)
            add_relationship(src_node=result.get("a"), dst_node=result.get("av"), rel_type="HAS_VALUE", at=at)
            add_relationship(src_node=result.get("a"), dst_node=result.get("isv"), rel_type="IS_VISIBLE", at=at)
            add_relationship(src_node=result.get("a"), dst_node=result.get("isp"), rel_type="IS_PROTECTED", at=at)
            rel_ids_to_update.extend(
                [result.get("r2").id, result.get("r3").id, result.get("rel_isv").id, result.get("rel_isp").id]
            )

            if result.get("source"):
                add_relationship(src_node=result.get("a"), dst_node=result.get("source"), rel_type="HAS_SOURCE", at=at)
                rel_ids_to_update.append(result.get("rel_source").id)

        # ---------------------------------------------
        # ATTRIBUTES
        # ---------------------------------------------
        query = DiffAttributeQuery(branch=self).execute()

        for result in query.get_results_group_by_branch_attribute():

            node_id = result.get("n").get("uuid")
            attr_name = result.get("a").get("name")

            # Ignore attributes that are associated with a new node
            if node_id in node_uuid_already_merged:
                continue

            # For now only consider the item that have been changed in the branch
            if result.get("r").get("branch") != self.name:
                continue

            # Need to find the current valid relationship in main and update its time
            current_attr_query = NodeListGetAttributeQuery(
                ids=[node_id], fields={attr_name: True}, branch=default_branch, at=at, include_source=True
            ).execute()
            current_attr = current_attr_query.get_result_by_id_and_name(node_id, attr_name)

            PROPERTY_TYPE_MAPPING = {
                "HAS_VALUE": ("r2", "av"),
                "HAS_OWNER": ("rel_owner", "owner"),
                "HAS_SOURCE": ("rel_source", "source"),
                "IS_PROTECTED": ("rel_isp", "isp"),
                "IS_VISIBLE": ("rel_isv", "isv"),
            }

            current_rel_name = PROPERTY_TYPE_MAPPING[result.get("r").type][0]

            add_relationship(src_node=result.get("a"), dst_node=result.get("ap"), rel_type=result.get("r").type, at=at)
            rel_ids_to_update.extend([result.get("r").id, current_attr.get(current_rel_name).id])

        # ---------------------------------------------
        # RELATIONSHIPS
        # ---------------------------------------------
        query = DiffRelationshipQuery(branch=self)
        query.execute()

        for result in query.get_results_deduplicated():

            # For now only consider the item that have been changed in the branch
            if result.get("r1").get("branch") != self.name:
                continue

            add_relationship(
                src_node=result.get("sn"), dst_node=result.get("rel"), rel_type=result.get("r1").type, at=at
            )
            add_relationship(
                src_node=result.get("dn"), dst_node=result.get("rel"), rel_type=result.get("r2").type, at=at
            )
            rel_ids_to_update.append(result.get("r1").id)
            rel_ids_to_update.append(result.get("r2").id)

        update_relationships_to(ids=rel_ids_to_update, to=at)

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
            created_new_node = False  # noqa
            if not node or node.node_uuid != result.get("n").get("uuid"):
                created_new_node = True  # noqa
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
