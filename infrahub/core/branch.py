from __future__ import annotations
from collections import defaultdict

from dataclasses import dataclass
from typing import List, Dict, Set, Any, Union, Optional, Generator

from pydantic import validator

import infrahub.config as config
from infrahub.core.constants import RelationshipStatus, DiffAction
from infrahub.core.query import Query, QueryType
from infrahub.core.query.diff import DiffNodeQuery, DiffAttributeQuery, DiffRelationshipQuery
from infrahub.core.query.attribute import AttributeGetValueQuery
from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.core.node.standard import StandardNode
from infrahub.core.constants import RelationshipStatus
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

    def validate(self) -> set(bool, List[str]):
        """Validate if a branch is eligible to be merged.
        - Must be conflict free both for data and repository
        - All checks must pass
        - Check schema changes

        Need to support with and without rebase

        Need to return a list of violations, must be multiple
        """

        passed = True
        messages = []

        # Check the diff and ensure the branch doesn't have some conflict
        if conflicts := self.diff().get_conflicts():
            passed = False
            for conflict in conflicts:
                messages.append(f"Conflict detected at {'/'.join(conflict)}")

        from infrahub.core.manager import NodeManager

        # For all repositories in this branch, run all checks
        repos = NodeManager.query("Repository", branch=self)
        for repo in repos:
            result, errors = repo.run_checks()
            if not result:
                messages.extend(errors)
                passed = False

        return passed, messages

    def diff(self, diff_from: Union[str, Timestamp] = None, diff_to: Union[str, Timestamp] = None ) -> Diff:
        return Diff(branch=self, diff_from=diff_from, diff_to=diff_to)

    def merge(self, at: Union[str, Timestamp]=None):
        """Merge the current branch into main."""

        passed, _ = self.validate()
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
        query = DiffRelationshipQuery(branch=self).execute()

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
class ValueElement:
    previous: Any
    new: Any


@dataclass
class AttributePropertyDiffElement:
    branch: str
    type: str
    action: str
    rel_id: int
    # value: ValueElement
    changed_at: Timestamp


@dataclass
class NodeAttributeDiffElement:
    id: str
    name: str
    action: str
    rel_id: int
    changed_at: Timestamp
    properties: Dict[str, AttributePropertyDiffElement]


@dataclass
class NodeDiffElement:
    branch: str
    labels: List[str]
    id: str
    action: str
    rel_id: int
    changed_at: Timestamp
    attributes: Dict[str, NodeAttributeDiffElement]


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

    diff_from: Timestamp
    diff_to: Timestamp

    def __init__(
        self,
        branch: Branch,
        branch_only: bool = False,
        diff_from: Union[str, Timestamp] = None,
        diff_to: Union[str, Timestamp] = None,
    ):
        self.branch = branch

        self.branch_only = branch_only

        if diff_from:
            self.diff_from = Timestamp(diff_from)
        elif not diff_from and not self.branch.is_default:
            self.diff_from = Timestamp(self.branch.branched_from)
        else:
            raise ValueError("diff_from is mandatory when the diffing on the main branch.")

        # If Diff_to is not defined it will automatically select the current time.
        self.diff_to = Timestamp(diff_to)

        if self.diff_to < self.diff_from:
            raise ValueError("diff_to must be later than diff_from")

        # # Internal cache to avoid re-querying everything
        # self._nodes: List[NodeDiffElement] = None

        # Results organized by Branch
        self._results: Dict[str, dict] = defaultdict(lambda: dict(nodes={}, relationships={}, files={}))

        self._calculated_diff_nodes_at = None
        self._calculated_diff_rels_at = None
        self._calculated_diff_files_at = None

    @property
    def has_conflict(self) -> bool:
        """Return True if the same path has been modified on multiple branches. False otherwise"""

        if self.get_conflicts():
            return True

        return False

    @property
    def has_changes(self) -> bool:
        """Return True if the diff has identified some changes, False otherwise."""

        for _, paths in self.get_modified_paths().items():
            if paths:
                return True

        return False

    def get_conflicts(self):

        if self.branch_only:
            return []

        paths = self.get_modified_paths()

        # For now we assume that we can only have 2 branches but in the future we might need to support more
        branches = list(paths.keys())

        # Since we have 2 sets or tuple, we can quickly calculate the intersection using set(A) & set(B)
        conflicts = paths[branches[0]] & paths[branches[1]]

        return conflicts


    def get_modified_paths(self):

        paths = defaultdict(set)

        for branch_name, data in self.get_nodes().items():
            if self.branch_only and branch_name != self.branch.name:
                continue

            for node_id, node in data.items():
                for attr_name, attr in node.attributes.items():
                    for prop_type, prop in attr.properties.items():
                        paths[branch_name].add(("node", node_id, attr_name, prop_type))

        # TODO Relationships and Files

        return paths

    def get_nodes(self):

        if not self._calculated_diff_nodes_at:
            self._calculate_diff_nodes()

        return {branch_name: data["nodes"] for branch_name, data in self._results.items()}

    def _calculate_diff_nodes(self):
        """Calculate the diff for all the nodes and attributes.

        The results will be stored in self._results organized by branch.
        """

        # Query all the nodes and the attributes that have been modified in the branch between the two timestamps.
        query_nodes = DiffNodeQuery(branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to).execute()
        query_attrs = DiffAttributeQuery(branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to).execute()

        results = {}

        # node_ids_to_skip = []

        # Process nodes that have been Added or Removed first
        for result in query_nodes.get_results():
            node_id = result.get("n").get("uuid")

            node_to = None
            if result.get("r").get("to"):
                node_to = Timestamp(result.get("r").get("to"))

            # If to_time is defined and if smaller than the diff_to time,
            #   then this is not the correct relationship to define this node
            #   NOTE would it make sense to move this logic into the Query itself ?
            if node_to and node_to < self.diff_to:
                continue

            branch_status = result.get("r").get("status")
            branch_name = result.get("b").get("name")
            from_time = result.get("r").get("from")

            item = {
                "branch": result.get("b").get("name"),
                "labels": list(result.get("n").labels),
                "id": node_id,
                "attributes": {},
                "rel_id": result.get("r").id,
                "changed_at": Timestamp(from_time),
            }

            # Need to revisit this part altogether to properly account for deleted node.
            if branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED.value
            elif branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED.value

            self._results[branch_name]["nodes"][node_id] = NodeDiffElement(**item)

        # Process Attributes that have been Added, Updated or Removed
        for result in query_attrs.get_results():

            node_id = result.get("n").get("uuid")
            branch_name = result.get("r2").get("branch")

            # Check if the node already exist, if not it means it was not added or removed so it was updated
            if node_id not in self._results[branch_name]["nodes"].keys():

                item = {
                    "labels": list(result.get("n").labels),
                    "id": node_id,
                    "attributes": {},
                    "changed_at": None,
                    "action": DiffAction.UPDATED.value,
                    "rel_id": None,
                    "branch": None,
                }

                self._results[branch_name]["nodes"][node_id] = NodeDiffElement(**item)

            # Check if the Attribute is already present or if it was added during this time frame.
            attr_name = result.get("a").get("name")
            if attr_name not in self._results[branch_name]["nodes"][node_id].attributes.keys():

                item = {
                    "id": result.get("a").get("uuid"),
                    "name": attr_name,
                    "rel_id": result.get("r1").id,
                    "properties": {},
                }

                attr_to = None
                attr_from = None
                branch_status = result.get("r1").get("status")

                if result.get("r1").get("to"):
                    attr_to = Timestamp(result.get("r1").get("to"))
                if result.get("r1").get("from"):
                    attr_from = Timestamp(result.get("r1").get("from"))

                if attr_to and attr_to < self.diff_to:
                    continue

                if attr_from > self.diff_from and branch_status == RelationshipStatus.ACTIVE.value:
                    item["action"] = DiffAction.ADDED.value
                    item["changed_at"] = attr_from
                elif attr_from > self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                    item["action"] = DiffAction.REMOVED.value
                    item["changed_at"] = attr_from
                else:
                    item["action"] = DiffAction.UPDATED.value
                    item["changed_at"] = None

                self._results[branch_name]["nodes"][node_id].attributes[attr_name] = NodeAttributeDiffElement(**item)

            # import pdb
            # pdb.set_trace()

            # Process the Property of the Attribute
            prop_to = None
            prop_from = None
            branch_status = result.get("r2").get("status")

            if result.get("r2").get("to"):
                prop_to = Timestamp(result.get("r2").get("to"))
            if result.get("r2").get("from"):
                prop_from = Timestamp(result.get("r2").get("from"))

            if prop_to and prop_to < self.diff_to:
                continue

            prop_type = result.get("r2").type
            item = {
                "type": prop_type,
                "branch": branch_name,
                "rel_id": result.get("r2").id,
            }

            if prop_from > self.diff_from and branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED.value
                item["changed_at"] = prop_from
            elif prop_from > self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED.value
                item["changed_at"] = prop_from
            else:
                item["action"] = DiffAction.UPDATED.value
                item["changed_at"] = prop_from

            self._results[branch_name]["nodes"][node_id].attributes[attr_name].properties[
                prop_type
            ] = AttributePropertyDiffElement(**item)

        self._calculated_diff_nodes_at = Timestamp()

    def get_relationships(self) -> List[RelationshipDiffElement]:

        results = []

        query = DiffRelationshipQuery(branch=self.branch).execute()

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
        from infrahub.core.manager import NodeManager

        # Collect all Repositories in Main because we'll need the commit in Main for each one.
        repos_in_main = {repo.id: repo for repo in NodeManager.query("Repository")}

        for repo in NodeManager.query("Repository", branch=self.branch):

            # Check if the repo, exist in main, if not ignore this repo
            if repo.id not in repos_in_main:
                continue

            repo_in_main = repos_in_main[repo.id]
            changed_files = repo.calculate_diff_with_commit(repo_in_main.commit.value)

            if not changed_files:
                continue

            results.append(
                {
                    "branch": repo.branch.name,
                    "repository_uuid": repo.uuid,
                    "repository_name": repo.name.value,
                    "files": changed_files,
                }
            )

        return results
