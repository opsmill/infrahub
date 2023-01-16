from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from pydantic import validator

import infrahub.config as config
from infrahub.core.constants import DiffAction, RelationshipStatus
from infrahub.core.node.standard import StandardNode
from infrahub.core.query import Query, QueryType
from infrahub.core.query.diff import (
    DiffAttributeQuery,
    DiffNodeQuery,
    DiffRelationshipPropertyQuery,
    DiffRelationshipQuery,
)
from infrahub.core.query.node import (
    NodeDeleteQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
)
from infrahub.core.query.relationship import RelationshipListGetPropertiesQuery
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import (
    add_relationship,
    element_id_to_id,
    update_relationships_to,
)
from infrahub.database import execute_read_query_async
from infrahub.exceptions import BranchNotFound
from infrahub.message_bus.events import (
    CheckMessageAction,
    GitMessageAction,
    InfrahubCheckRPC,
    InfrahubGitRPC,
    RPCStatusCode,
)
from infrahub.message_bus.rpc import InfrahubRpcClient

if TYPE_CHECKING:
    from neo4j import AsyncSession


class AddNodeToBranch(Query):

    name: str = "node_add_to_branch"
    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, node_id: int, *args, **kwargs):

        self.node_id = node_id
        super().__init__(*args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        query = """
        MATCH (b:Branch { name: $branch })
        MATCH (d) WHERE ID(d) = $node_id
        WITH b,d
        CREATE (d)-[r:IS_PART_OF { from: $now, to: null, status: $status }]->(b)
        RETURN ID(r)
        """

        self.params["node_id"] = element_id_to_id(self.node_id)
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
    async def get_by_name(cls, name: str, session: AsyncSession) -> Branch:

        query = """
        MATCH (n:Branch)
        WHERE n.name = $name
        RETURN n
        """

        params = {"name": name}

        results = await execute_read_query_async(session=session, query=query, params=params)

        if len(results) == 0:
            raise BranchNotFound(identifier=name)

        return cls._convert_node_to_obj(results[0].values()[0])

    async def get_origin_branch(self, session: AsyncSession) -> Branch:

        from infrahub.core import get_branch

        return await get_branch(self.origin_branch, session=session)

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
    ) -> Tuple[str, Dict]:

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
    ) -> Tuple[List, Dict]:

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

    def get_query_filter_path(self, at: Union[Timestamp, str] = None) -> Tuple[str, Dict]:

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

    async def rebase(self, session: Optional[AsyncSession] = None):
        """Rebase the current Branch with its origin branch"""

        self.branched_from = Timestamp().to_string()
        await self.save(session=session)

        # Update the branch in the registry after the rebase
        from infrahub.core import registry

        registry.branch[self.name] = self

    async def validate(
        self, rpc_client: InfrahubRpcClient, session: Optional[AsyncSession] = None
    ) -> set(bool, List[str]):
        """Validate if a branch is eligible to be merged.
        - Must be conflict free both for data and repository
        - All checks must pass
        - Check schema changes

        Need to support with and without rebase

        Need to return a list of violations, must be multiple
        """

        passed = True
        messages = []
        tasks = []

        # Check the diff and ensure the branch doesn't have some conflict
        diff = await self.diff(session=session)
        if conflicts := await diff.get_conflicts(session=session):
            passed = False
            for conflict in conflicts:
                messages.append(f"Conflict detected at {'/'.join(conflict)}")

        from infrahub.core.manager import NodeManager

        # For all repositories in this branch, run all checks
        repos = await NodeManager.query(schema="Repository", branch=self, session=session)

        # Collecting all the checks from all the repopository
        for repo in repos:
            for rel_check in repo.checks.get():
                check = await rel_check.get_peer(session=session)

                tasks.append(
                    rpc_client.call(
                        message=InfrahubCheckRPC(
                            action=CheckMessageAction.PYTHON,
                            repository=repo,
                            branch_name=self.name,
                            check_location=check.file_path.value,
                            check_name=check.class_name.value,
                            name=check.name,
                            commit=repo.commit.value,
                        )
                    )
                )

        responses = await asyncio.gather(*tasks)

        # Collecting all the responses and the logs from all tasks
        for response in responses:
            if response.status != RPCStatusCode.OK.value:
                continue

            if not response.response["passed"]:
                passed = False
                messages.extend([error["message"] for error in response.response["errors"]])

        return passed, messages

    async def diff(
        self,
        diff_from: Union[str, Timestamp] = None,
        diff_to: Union[str, Timestamp] = None,
        session: Optional[AsyncSession] = None,
    ) -> Diff:
        return await Diff.init(branch=self, diff_from=diff_from, diff_to=diff_to, session=session)

    async def merge(
        self, rpc_client: InfrahubRpcClient, at: Union[str, Timestamp] = None, session: Optional[AsyncSession] = None
    ):
        """Merge the current branch into main."""

        passed, _ = await self.validate(rpc_client=rpc_client, session=session)
        if not passed:
            raise Exception(f"Unable to merge the branch '{self.name}', validation failed")

        if self.name == config.SETTINGS.main.default_branch:
            raise Exception(f"Unable to merge the branch '{self.name}' into itself")

        from infrahub.core import registry
        from infrahub.core.manager import NodeManager

        rel_ids_to_update = []

        default_branch = registry.branch[config.SETTINGS.main.default_branch]

        at = Timestamp(at)

        diff = await Diff.init(branch=self, session=session)
        nodes = await diff.get_nodes(session=session)

        origin_nodes_query = await NodeListGetInfoQuery.init(
            session=session, ids=list(nodes[self.name].keys()), branch=default_branch
        )
        await origin_nodes_query.execute(session=session)
        origin_nodes = {
            node.get("n").get("uuid"): node for node in origin_nodes_query.get_results_group_by(("n", "uuid"))
        }

        # ---------------------------------------------
        # NODES
        # ---------------------------------------------
        for node_id, node in nodes[self.name].items():

            if node.action == DiffAction.ADDED.value:
                query = await AddNodeToBranch.init(session=session, node_id=node.db_id, branch=default_branch)
                await query.execute(session=session)
                rel_ids_to_update.append(node.rel_id)

            elif node.action == DiffAction.REMOVED.value:
                query = await NodeDeleteQuery.init(session=session, branch=default_branch, node_id=node_id, at=at)
                await query.execute(session=session)
                rel_ids_to_update.extend([node.rel_id, origin_nodes[node_id].get("rb").element_id])

            for _, attr in node.attributes.items():

                if attr.action == DiffAction.ADDED.value:
                    await add_relationship(
                        src_node_id=node.db_id,
                        dst_node_id=attr.db_id,
                        rel_type="HAS_ATTRIBUTE",
                        at=at,
                        branch_name=default_branch.name,
                        session=session,
                    )
                    rel_ids_to_update.append(attr.rel_id)

                elif attr.action == DiffAction.REMOVED.value:
                    await add_relationship(
                        src_node_id=node.db_id,
                        dst_node_id=attr.db_id,
                        rel_type="HAS_ATTRIBUTE",
                        branch_name=default_branch.name,
                        at=at,
                        status=RelationshipStatus.DELETED,
                        session=session,
                    )
                    rel_ids_to_update.extend([attr.rel_id, attr.origin_rel_id])

                elif attr.action == DiffAction.UPDATED.value:
                    pass

                for prop_type, prop in attr.properties.items():

                    if prop.action == DiffAction.ADDED.value:
                        await add_relationship(
                            src_node_id=attr.db_id,
                            dst_node_id=prop.db_id,
                            rel_type=prop_type,
                            at=at,
                            branch_name=default_branch.name,
                            session=session,
                        )
                        rel_ids_to_update.append(prop.rel_id)

                    elif prop.action == DiffAction.UPDATED.value:

                        await add_relationship(
                            src_node_id=attr.db_id,
                            dst_node_id=prop.db_id,
                            rel_type=prop_type,
                            at=at,
                            branch_name=default_branch.name,
                            session=session,
                        )
                        rel_ids_to_update.extend([prop.rel_id, prop.origin_rel_id])

                    elif prop.action == DiffAction.REMOVED.value:
                        await add_relationship(
                            src_node_id=attr.db_id,
                            dst_node_id=prop.db_id,
                            rel_type=prop_type,
                            at=at,
                            branch_name=default_branch.name,
                            status=RelationshipStatus.DELETED,
                            session=session,
                        )
                        rel_ids_to_update.extend([prop.rel_id, prop.origin_rel_id])

        # ---------------------------------------------
        # RELATIONSHIPS
        # ---------------------------------------------
        rels = await diff.get_relationships(session=session)

        for rel_name in rels[self.name].keys():
            for rel_id, rel in rels[self.name][rel_name].items():
                for node in rel.nodes.values():
                    if rel.action in [DiffAction.ADDED.value, DiffAction.REMOVED.value]:
                        rel_status = RelationshipStatus.ACTIVE
                        if rel.action == DiffAction.REMOVED.value:
                            rel_status = RelationshipStatus.DELETED

                        await add_relationship(
                            src_node_id=node.db_id,
                            dst_node_id=rel.db_id,
                            rel_type="IS_RELATED",
                            at=at,
                            branch_name=default_branch.name,
                            status=rel_status,
                            session=session,
                        )
                        rel_ids_to_update.append(node.rel_id)

                for prop_type, prop in rel.properties.items():

                    rel_status = RelationshipStatus.ACTIVE
                    if prop.action == DiffAction.REMOVED.value:
                        rel_status = RelationshipStatus.DELETED

                    await add_relationship(
                        src_node_id=rel.db_id,
                        dst_node_id=prop.db_id,
                        rel_type=prop.type,
                        at=at,
                        branch_name=default_branch.name,
                        session=session,
                    )
                    rel_ids_to_update.append(prop.rel_id)

                    if rel.action in [DiffAction.UPDATED.value, DiffAction.REMOVED.value]:
                        rel_ids_to_update.append(prop.origin_rel_id)

        await update_relationships_to(ids=rel_ids_to_update, to=at, session=session)

        # ---------------------------------------------
        # FILES
        # ---------------------------------------------

        # Collect all Repositories in Main because we'll need the commit in Main for each one.
        repos_in_main_list = await NodeManager.query(schema="Repository", session=session)
        repos_in_main = {repo.id: repo for repo in repos_in_main_list}
        tasks = []

        repos_in_branch_list = await NodeManager.query(schema="Repository", session=session, branch=self)
        for repo in repos_in_branch_list:

            # Check if the repo, exist in main, if not ignore this repo
            if repo.id not in repos_in_main:
                continue

            repos_in_main[repo.id]
            # changed_files = repo.calculate_diff_with_commit(repo_in_main.commit.value)

            # if not changed_files:
            #     continue

            tasks.append(
                rpc_client.call(
                    message=InfrahubGitRPC(
                        action=GitMessageAction.MERGE, repository=repo, params={"branch_name": self.name}
                    )
                )
            )

        await asyncio.gather(*tasks)

        await self.rebase(session=session)


@dataclass
class ValueElement:
    previous: Any
    new: Any


@dataclass
class PropertyDiffElement:
    branch: str
    type: str
    action: DiffAction
    db_id: str
    rel_id: str
    origin_rel_id: Optional[str]
    # value: ValueElement
    changed_at: Timestamp


@dataclass
class NodeAttributeDiffElement:
    id: UUID
    name: str
    action: DiffAction
    db_id: str
    rel_id: str
    origin_rel_id: Optional[str]
    changed_at: Timestamp
    properties: Dict[str, PropertyDiffElement]


@dataclass
class NodeDiffElement:
    branch: str
    labels: List[str]
    id: UUID
    action: DiffAction
    db_id: str
    rel_id: str
    changed_at: Timestamp
    attributes: Dict[str, NodeAttributeDiffElement]


@dataclass
class AttributeDiffElement:
    branch: str
    node_labels: List[str]
    node_uuid: str
    attr_uuid: str
    attr_name: str
    action: DiffAction
    changed_at: str


@dataclass
class RelationshipEdgeNodeDiffElement:
    id: UUID
    db_id: int
    rel_id: int
    labels: List[str]


@dataclass
class RelationshipDiffElement:
    branch: str
    id: UUID
    db_id: str
    name: str
    action: DiffAction
    nodes: Dict[str, RelationshipEdgeNodeDiffElement]
    properties: Dict[str, PropertyDiffElement]
    changed_at: str


@dataclass
class RelationshipDiffElementOld:
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
        origin_branch: Branch,
        branch_only: bool = False,
        diff_from: Union[str, Timestamp] = None,
        diff_to: Union[str, Timestamp] = None,
    ):
        self.branch = branch
        self.branch_only = branch_only
        self.origin_branch = origin_branch

        if diff_from:
            self.diff_from = Timestamp(diff_from)
        elif not diff_from and not self.branch.is_default:
            self.diff_from = Timestamp(self.branch.branched_from)
        else:
            raise ValueError(f"diff_from is mandatory when diffing on the default branch `{self.branch.name}`.")

        # If diff_to is not defined it will automatically select the current time.
        self.diff_to = Timestamp(diff_to)

        if self.diff_to < self.diff_from:
            raise ValueError("diff_to must be later than diff_from")

        # Results organized by Branch
        self._results: Dict[str, dict] = defaultdict(lambda: dict(nodes={}, rels=defaultdict(lambda: dict()), files={}))

        self._calculated_diff_nodes_at = None
        self._calculated_diff_rels_at = None
        self._calculated_diff_files_at = None

    @classmethod
    async def init(
        cls,
        branch: Branch,
        branch_only: bool = False,
        diff_from: Union[str, Timestamp] = None,
        diff_to: Union[str, Timestamp] = None,
        session: Optional[AsyncSession] = None,
    ):

        origin_branch = await branch.get_origin_branch(session=session)

        return cls(
            branch=branch, origin_branch=origin_branch, branch_only=branch_only, diff_from=diff_from, diff_to=diff_to
        )

    async def has_conflict(self, session: AsyncSession) -> bool:
        """Return True if the same path has been modified on multiple branches. False otherwise"""

        if await self.get_conflicts(session=session):
            return True

        return False

    async def has_changes(self, session: AsyncSession) -> bool:
        """Return True if the diff has identified some changes, False otherwise."""

        mpaths = await self.get_modified_paths(session=session)
        for _, paths in mpaths.items():
            if paths:
                return True

        return False

    async def get_conflicts(self, session: AsyncSession):

        if self.branch_only:
            return []

        paths = await self.get_modified_paths(session=session)

        # For now we assume that we can only have 2 branches but in the future we might need to support more
        branches = list(paths.keys())

        # if we don't have at least 2 branches returned we can safely assumed there is no conflict
        if len(branches) < 2:
            return []

        # Since we have 2 sets or tuple, we can quickly calculate the intersection using set(A) & set(B)
        return paths[branches[0]] & paths[branches[1]]

    async def get_modified_paths(self, session: AsyncSession) -> Dict[str, set]:
        """Return a list of all the modified paths per branch."""

        paths = defaultdict(set)

        nodes = await self.get_nodes(session=session)
        for branch_name, data in nodes.items():
            if self.branch_only and branch_name != self.branch.name:
                continue

            for node_id, node in data.items():
                for attr_name, attr in node.attributes.items():
                    for prop_type, prop in attr.properties.items():
                        paths[branch_name].add(("node", node_id, attr_name, prop_type))

        rels = await self.get_relationships(session=session)
        for branch_name, data in rels.items():
            if self.branch_only and branch_name != self.branch.name:
                continue

            for rel_name, rels in data.items():
                for rel_id, rel in rels.items():
                    for prop_type, prop in rel.properties.items():
                        paths[branch_name].add(("relationships", rel_name, rel_id, prop_type))

        # TODO Files

        return paths

    async def get_nodes(self, session: AsyncSession) -> Dict[str, Dict[str, NodeDiffElement]]:

        if not self._calculated_diff_nodes_at:
            await self._calculate_diff_nodes(session=session)

        return {branch_name: data["nodes"] for branch_name, data in self._results.items()}

    async def _calculate_diff_nodes(self, session: AsyncSession):
        """Calculate the diff for all the nodes and attributes.

        The results will be stored in self._results organized by branch.
        """

        # Query all the nodes and the attributes that have been modified in the branch between the two timestamps.
        query_nodes = await DiffNodeQuery.init(
            session=session, branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to
        )
        await query_nodes.execute(session=session)
        query_attrs = await DiffAttributeQuery.init(
            session=session, branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to
        )
        await query_attrs.execute(session=session)

        attrs_to_query = {"nodes": set(), "fields": set()}

        # ------------------------------------------------------------
        # Process nodes that have been Added or Removed first
        # ------------------------------------------------------------
        for result in query_nodes.get_results():
            node_id = result.get("n").get("uuid")

            node_to = None
            if result.get("r").get("to"):
                node_to = Timestamp(result.get("r").get("to"))

            # If to_time is defined and is smaller than the diff_to time,
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
                "db_id": result.get("n").element_id,
                "attributes": {},
                "rel_id": result.get("r").element_id,
                "changed_at": Timestamp(from_time),
            }

            if branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED.value
            elif branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED.value

            self._results[branch_name]["nodes"][node_id] = NodeDiffElement(**item)

        # ------------------------------------------------------------
        # Process Attributes that have been Added, Updated or Removed
        #  We don't process the properties right away, instead we'll identify the node that mostlikely already exist
        #  and we'll query the current value to fully understand what we need to do with it.
        # ------------------------------------------------------------
        for result in query_attrs.get_results():

            node_id = result.get("n").get("uuid")
            branch_name = result.get("r2").get("branch")

            # Check if the node already exist, if not it means it was not added or removed so it was updated
            if node_id not in self._results[branch_name]["nodes"].keys():

                item = {
                    "labels": list(result.get("n").labels),
                    "id": node_id,
                    "db_id": result.get("n").element_id,
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

                node = self._results[branch_name]["nodes"][node_id]
                item = {
                    "id": result.get("a").get("uuid"),
                    "db_id": result.get("a").element_id,
                    "name": attr_name,
                    "rel_id": result.get("r1").element_id,
                    "properties": {},
                    "origin_rel_id": None,
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

                if (
                    node.action == DiffAction.ADDED.value
                    and attr_from >= self.diff_from
                    and branch_status == RelationshipStatus.ACTIVE.value
                ):
                    item["action"] = DiffAction.ADDED.value
                    item["changed_at"] = attr_from

                elif attr_from >= self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                    item["action"] = DiffAction.REMOVED.value
                    item["changed_at"] = attr_from

                    attrs_to_query["nodes"].add(node_id)
                    attrs_to_query["fields"].add(attr_name)
                else:
                    item["action"] = DiffAction.UPDATED.value
                    item["changed_at"] = None

                    attrs_to_query["nodes"].add(node_id)
                    attrs_to_query["fields"].add(attr_name)

                self._results[branch_name]["nodes"][node_id].attributes[attr_name] = NodeAttributeDiffElement(**item)

        # ------------------------------------------------------------
        # Query the current value for all attributes that have been updated
        #  Currently we are only using the result of this query to understand if a
        # ------------------------------------------------------------
        origin_attr_query = await NodeListGetAttributeQuery.init(
            session=session,
            ids=list(attrs_to_query["nodes"]),
            branch=self.origin_branch,
            at=self.diff_to,
            include_source=True,
        )
        await origin_attr_query.execute(session=session)

        for result in query_attrs.get_results():

            node_id = result.get("n").get("uuid")
            branch_name = result.get("r2").get("branch")
            branch_status = result.get("r2").get("status")
            attr_name = result.get("a").get("name")
            prop_type = result.get("r2").type

            origin_attr = origin_attr_query.get_result_by_id_and_name(node_id, attr_name)
            origin_rel_name = origin_attr_query.property_type_mapping[prop_type][0]

            # Process the Property of the Attribute
            prop_to = None
            prop_from = None

            if result.get("r2").get("to"):
                prop_to = Timestamp(result.get("r2").get("to"))
            if result.get("r2").get("from"):
                prop_from = Timestamp(result.get("r2").get("from"))

            if prop_to and prop_to < self.diff_to:
                continue

            item = {
                "type": prop_type,
                "branch": branch_name,
                "db_id": result.get("ap").element_id,
                "rel_id": result.get("r2").element_id,
                "origin_rel_id": None,
            }

            if origin_attr:
                item["origin_rel_id"] = origin_attr.get(origin_rel_name).element_id

            if not origin_attr and prop_from >= self.diff_from and branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED.value
                item["changed_at"] = prop_from
            elif prop_from >= self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED.value
                item["changed_at"] = prop_from
            else:
                item["action"] = DiffAction.UPDATED.value
                item["changed_at"] = prop_from

            self._results[branch_name]["nodes"][node_id].attributes[attr_name].origin_rel_id = result.get(
                "r1"
            ).element_id
            self._results[branch_name]["nodes"][node_id].attributes[attr_name].properties[
                prop_type
            ] = PropertyDiffElement(**item)

        self._calculated_diff_nodes_at = Timestamp()

    async def get_relationships(self, session: AsyncSession) -> Dict[str, Dict[str, RelationshipDiffElement]]:

        if not self._calculated_diff_rels_at:
            await self._calculated_diff_rels(session=session)

        return {branch_name: data["rels"] for branch_name, data in self._results.items()}

    async def _calculated_diff_rels(self, session: AsyncSession):
        """Calculate the diff for all the relationships between Nodes.

        The results will be stored in self._results organized by branch.
        """
        # Query the diff on the main path
        query_rels = await DiffRelationshipQuery.init(
            session=session, branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to
        )
        await query_rels.execute(session=session)

        # Query the diff on the properties
        query_props = await DiffRelationshipPropertyQuery.init(
            session=session, branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to
        )
        await query_props.execute(session=session)

        rel_ids_to_query = []

        # ------------------------------------------------------------
        # Process the main path of the relationships
        # to identify the relationship that have been added or deleted
        # ------------------------------------------------------------
        for result in query_rels.get_results():

            branch_name = result.get("r1").get("branch")
            branch_status = result.get("r1").get("status")
            rel_name = result.get("rel").get("type")
            rel_id = result.get("rel").get("uuid")

            src_node_id = result.get("sn").get("uuid")
            dst_node_id = result.get("dn").get("uuid")

            from_time = Timestamp(result.get("r1").get("from"))
            # to_time = result.get("r1").get("to", None)

            item = dict(
                branch=branch_name,
                id=rel_id,
                db_id=result.get("rel").element_id,
                name=rel_name,
                nodes={
                    src_node_id: RelationshipEdgeNodeDiffElement(
                        id=src_node_id,
                        db_id=result.get("sn").element_id,
                        rel_id=result.get("r1").element_id,
                        labels=result.get("sn").labels,
                    ),
                    dst_node_id: RelationshipEdgeNodeDiffElement(
                        id=src_node_id,
                        db_id=result.get("dn").element_id,
                        rel_id=result.get("r2").element_id,
                        labels=result.get("dn").labels,
                    ),
                },
                properties={},
            )

            # FIXME Need to revisit changed_at, mostlikely not accurate. More of a placeholder at this point
            if branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED.value
                item["changed_at"] = from_time
            elif branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED.value
                item["changed_at"] = from_time
                rel_ids_to_query.append(rel_id)
            else:
                raise Exception(f"Unexpected value for branch_status: {branch_status}")

            self._results[branch_name]["rels"][rel_name][rel_id] = RelationshipDiffElement(**item)

        # ------------------------------------------------------------
        # Process the properties of the relationships that changed
        # ------------------------------------------------------------
        for result in query_props.get_results():

            branch_name = result.get("r3").get("branch")
            branch_status = result.get("r3").get("status")
            rel_name = result.get("rel").get("type")
            rel_id = result.get("rel").get("uuid")

            # Check if the relationship already exist, if not we need to create it
            if rel_id in self._results[branch_name]["rels"][rel_name]:
                continue

            src_node_id = result.get("sn").get("uuid")
            dst_node_id = result.get("dn").get("uuid")

            item = dict(
                id=rel_id,
                db_id=result.get("rel").element_id,
                name=rel_name,
                nodes={
                    src_node_id: RelationshipEdgeNodeDiffElement(
                        id=src_node_id,
                        db_id=result.get("sn").element_id,
                        rel_id=result.get("r1").element_id,
                        labels=result.get("sn").labels,
                    ),
                    dst_node_id: RelationshipEdgeNodeDiffElement(
                        id=src_node_id,
                        db_id=result.get("dn").element_id,
                        rel_id=result.get("r2").element_id,
                        labels=result.get("dn").labels,
                    ),
                },
                properties={},
                action=DiffAction.UPDATED.value,
                changed_at=None,
                branch=None,
            )

            self._results[branch_name]["rels"][rel_name][rel_id] = RelationshipDiffElement(**item)

            rel_ids_to_query.append(rel_id)

        # ------------------------------------------------------------
        # Query the current value of the relationships that have been updated
        # ------------------------------------------------------------
        origin_rel_properties_query = await RelationshipListGetPropertiesQuery.init(
            session=session, ids=rel_ids_to_query, branch=self.origin_branch, at=self.diff_to
        )
        await origin_rel_properties_query.execute(session=session)

        for result in query_props.get_results():

            branch_name = result.get("r3").get("branch")
            branch_status = result.get("r3").get("status")
            rel_name = result.get("rel").get("type")
            rel_id = result.get("rel").get("uuid")

            prop_type = result.get("r3").type
            prop_from = Timestamp(result.get("r3").get("from"))

            origin_prop = origin_rel_properties_query.get_by_id_and_prop_type(rel_id=rel_id, type=prop_type)
            prop = {
                "type": prop_type,
                "branch": branch_name,
                "db_id": result.get("rp").element_id,
                "rel_id": result.get("r3").element_id,
                "origin_rel_id": None,
            }

            if origin_prop:
                prop["origin_rel_id"] = origin_prop.get("r").element_id

            if not origin_prop and prop_from >= self.diff_from and branch_status == RelationshipStatus.ACTIVE.value:
                prop["action"] = DiffAction.ADDED.value
                prop["changed_at"] = prop_from
            elif prop_from >= self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                prop["action"] = DiffAction.REMOVED.value
                prop["changed_at"] = prop_from
            else:
                prop["action"] = DiffAction.UPDATED.value
                prop["changed_at"] = prop_from

            self._results[branch_name]["rels"][rel_name][rel_id].properties[prop_type] = PropertyDiffElement(**prop)

        self._calculated_diff_rels_at = Timestamp()

    async def get_files(self, session: AsyncSession):

        results = []
        from infrahub.core.manager import NodeManager

        # Collect all Repositories in Main because we'll need the commit in Main for each one.
        repos_in_main = {repo.id: repo for repo in await NodeManager.query(schema="Repository", session=session)}

        for repo in await NodeManager.query(schema="Repository", branch=self.branch, session=session):

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
