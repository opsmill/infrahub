from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field, validator

import infrahub.config as config
from infrahub.core.constants import GLOBAL_BRANCH_NAME, DiffAction, RelationshipStatus
from infrahub.core.manager import NodeManager
from infrahub.core.node.standard import StandardNode
from infrahub.core.query import Query, QueryType
from infrahub.core.query.diff import (
    DiffAttributeQuery,
    DiffNodePropertiesByIDSQuery,
    DiffNodeQuery,
    DiffRelationshipPropertiesByIDSRangeQuery,
    DiffRelationshipPropertyQuery,
    DiffRelationshipQuery,
)
from infrahub.core.query.node import NodeDeleteQuery, NodeListGetInfoQuery
from infrahub.core.registry import get_branch, registry
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import (
    add_relationship,
    element_id_to_id,
    update_relationships_to,
)
from infrahub.database import execute_read_query_async
from infrahub.exceptions import BranchNotFound, ValidationError
from infrahub.message_bus.events import (
    CheckMessageAction,
    GitMessageAction,
    InfrahubCheckRPC,
    InfrahubGitRPC,
    InfrahubRPCResponse,
    RPCStatusCode,
)

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.message_bus.rpc import InfrahubRpcClient

# pylint: disable=redefined-builtin,too-many-statements,too-many-lines,too-many-branches,too-many-public-methods


class ObjectConflict(BaseModel):
    type: str
    id: str
    path: str

    def __str__(self) -> str:
        return self.path


class ModifiedPath(BaseModel):
    type: str
    node_id: str
    element_name: Optional[str] = None
    property_name: Optional[str] = None
    peer_id: Optional[str] = None
    action: DiffAction

    def __eq__(self, other) -> bool:
        if not isinstance(other, ModifiedPath):
            return NotImplemented

        if self.modification_type != other.modification_type:
            return False

        if self.modification_type == "node":
            if self.action == other.action and self.action in [DiffAction.REMOVED, DiffAction.UPDATED]:
                return False

        return self.type == other.type and self.node_id == other.node_id

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ModifiedPath):
            return NotImplemented
        return str(self) < str(other)

    def __hash__(self):
        return hash((type(self),) + tuple(self.__dict__.values()))

    def __str__(self) -> str:
        identifier = f"{self.type}/{self.node_id}"
        if self.element_name:
            identifier += f"/{self.element_name}"

        if self.peer_id:
            identifier += f"/{self.peer_id}"

        if self.property_name and self.property_name == "HAS_VALUE":
            identifier += "/value"
        elif self.property_name:
            identifier += f"/property/{self.property_name}"

        return identifier

    @property
    def modification_type(self) -> str:
        if self.element_name:
            return "element"

        return "node"


class AddNodeToBranch(Query):
    name: str = "node_add_to_branch"
    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, node_id: int, *args, **kwargs):
        self.node_id = node_id
        super().__init__(*args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        query = """
        MATCH (root:Root)
        MATCH (d) WHERE ID(d) = $node_id
        WITH root,d
        CREATE (d)-[r:IS_PART_OF { branch: $branch, branch_level: $branch_level, from: $now, to: null, status: $status }]->(root)
        RETURN ID(r)
        """

        self.params["node_id"] = element_id_to_id(self.node_id)
        self.params["now"] = self.at.to_string()
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["status"] = RelationshipStatus.ACTIVE.value

        self.add_to_query(query)


class DeleteBranchRelationshipsQuery(Query):
    name: str = "delete_branch_relationships"
    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, branch_name: str, *args, **kwargs):
        self.branch_name = branch_name
        super().__init__(*args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        if config.SETTINGS.database.db_type == config.DatabaseType.MEMGRAPH:
            query = """
            MATCH p = (s)-[r]-(d)
            WHERE r.branch = $branch_name
            DELETE r
            """
        else:
            query = """
            MATCH p = (s)-[r]-(d)
            WHERE r.branch = $branch_name
            DELETE r
            WITH *
            UNWIND nodes(p) AS n
            MATCH (n)
            WHERE NOT exists((n)--())
            DELETE n
            """
        self.params["branch_name"] = self.branch_name
        self.add_to_query(query)


class Branch(StandardNode):
    name: str = Field(
        regex=rf"^[a-z][a-z0-9\-]+$|^{re.escape(GLOBAL_BRANCH_NAME)}$",
        max_length=32,
        min_length=3,
        description="Name of the branch (only lowercase, dash & alphanumeric characters are allowed)",
    )
    status: str = "OPEN"  # OPEN, CLOSED
    description: str = ""
    origin_branch: str = "main"
    branched_from: Optional[str] = None
    hierarchy_level: int = 2
    created_at: Optional[str] = None
    is_default: bool = False
    is_global: bool = False
    is_protected: bool = False
    is_data_only: bool = False
    schema_changed_at: Optional[str] = None
    schema_hash: Optional[int] = None

    ephemeral_rebase: bool = False

    _exclude_attrs: List[str] = ["id", "uuid", "owner", "ephemeral_rebase"]

    @validator("branched_from", pre=True, always=True)
    def set_branched_from(cls, value):  # pylint: disable=no-self-argument
        return Timestamp(value).to_string()

    @validator("created_at", pre=True, always=True)
    def set_created_at(cls, value):  # pylint: disable=no-self-argument
        return Timestamp(value).to_string()

    def update_schema_hash(self, at: Optional[Union[Timestamp, str]] = None) -> None:
        latest_schema = registry.schema.get_schema_branch(name=self.name)
        self.schema_changed_at = Timestamp(at).to_string()
        new_hash = hash(latest_schema)
        if new_hash == self.schema_hash:
            return False

        self.schema_hash = hash(latest_schema)
        return True

    @classmethod
    async def get_by_name(cls, name: str, session: AsyncSession) -> Branch:
        query = """
        MATCH (n:Branch)
        WHERE n.name = $name
        RETURN n
        """

        params = {"name": name}

        results = await execute_read_query_async(session=session, query=query, params=params, name="branch_get_by_name")

        if len(results) == 0:
            raise BranchNotFound(identifier=name)

        return cls._convert_node_to_obj(results[0].values()[0])

    @classmethod
    def isinstance(cls, obj: Any) -> bool:
        return isinstance(obj, cls)

    async def get_origin_branch(self, session: AsyncSession) -> Optional[Branch]:
        """Return the branch Object of the origin_branch."""
        if not self.origin_branch or self.origin_branch == self.name:
            return None

        return await get_branch(branch=self.origin_branch, session=session)

    def get_branches_in_scope(self) -> List[str]:
        """Return the list of all the branches that are constituing this branch.

        For now, either a branch is the default branch or it must inherit from it so we can only have 2 values at best
        But the idea is that it will change at some point in a future version.
        """
        default_branch = config.SETTINGS.main.default_branch
        if self.name == default_branch:
            return [self.name]

        return [default_branch, self.name]

    def get_branches_and_times_to_query(self, at: Optional[Union[Timestamp, str]] = None) -> Dict[frozenset, str]:
        """Return all the names of the branches that are constituing this branch with the associated times excluding the global branch"""

        at = Timestamp(at)

        if self.is_default:
            return {frozenset([self.name]): at.to_string()}

        time_default_branch = Timestamp(self.branched_from)

        # If we are querying before the beginning of the branch
        # the time for the main branch must be the time of the query
        if self.ephemeral_rebase or at < time_default_branch:
            time_default_branch = at

        return {
            frozenset([self.origin_branch]): time_default_branch.to_string(),
            frozenset([self.name]): at.to_string(),
        }

    def get_branches_and_times_to_query_global(
        self, at: Optional[Union[Timestamp, str]] = None
    ) -> Dict[frozenset, str]:
        """Return all the names of the branches that are constituing this branch with the associated times."""

        at = Timestamp(at)

        if self.is_default:
            return {frozenset((GLOBAL_BRANCH_NAME, self.name)): at.to_string()}

        time_default_branch = Timestamp(self.branched_from)

        # If we are querying before the beginning of the branch
        # the time for the main branch must be the time of the query
        if self.ephemeral_rebase or at < time_default_branch:
            time_default_branch = at

        return {
            frozenset((GLOBAL_BRANCH_NAME, self.origin_branch)): time_default_branch.to_string(),
            frozenset((GLOBAL_BRANCH_NAME, self.name)): at.to_string(),
        }

    def get_branches_and_times_for_range(
        self, start_time: Timestamp, end_time: Timestamp
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Return the names of the branches that are constituing this branch with the start and end times."""

        start = {}
        end = {}

        time_branched_from = Timestamp(self.branched_from)
        time_created_at = Timestamp(self.created_at)

        # Ensure start time is not older than the creation of the branch (time_created_at)
        time_query_start = start_time
        if start_time < time_created_at:
            time_query_start = time_created_at

        start[self.name] = time_query_start.to_string()

        # START
        if not self.is_default and time_query_start <= time_branched_from:
            start[self.origin_branch] = time_branched_from.to_string()
        elif not self.is_default and time_query_start > time_branched_from:
            start[self.origin_branch] = time_query_start.to_string()

        # END
        end[self.name] = end_time.to_string()
        if not self.is_default:
            end[self.origin_branch] = end_time.to_string()

        return start, end

    async def delete(self, session: AsyncSession) -> None:
        if self.is_default:
            raise ValidationError(f"Unable to delete {self.name} it is the default branch.")
        if self.is_global:
            raise ValidationError(f"Unable to delete {self.name} this is an internal branch.")
        await super().delete(session=session)
        query = await DeleteBranchRelationshipsQuery.init(session=session, branch_name=self.name)
        await query.execute(session=session)

    def get_query_filter_relationships(
        self, rel_labels: list, at: Optional[Union[Timestamp, str]] = None, include_outside_parentheses: bool = False
    ) -> Tuple[List, Dict]:
        """Generate a CYPHER Query filter based on a list of relationships to query a part of the graph at a specific time and on a specific branch."""

        filters = []
        params = {}

        if not isinstance(rel_labels, list):
            raise TypeError(f"rel_labels must be a list, not a {type(rel_labels)}")

        at = Timestamp(at)
        branches_times = self.get_branches_and_times_to_query_global(at=at)

        for idx, (branch_name, time_to_query) in enumerate(branches_times.items()):
            params[f"branch{idx}"] = list(branch_name)
            params[f"time{idx}"] = time_to_query

        for rel in rel_labels:
            filters_per_rel = []
            for idx, (branch_name, time_to_query) in enumerate(branches_times.items()):
                filters_per_rel.append(
                    f"({rel}.branch IN $branch{idx} AND {rel}.from <= $time{idx} AND {rel}.to IS NULL)"
                )
                filters_per_rel.append(
                    f"({rel}.branch IN $branch{idx} AND {rel}.from <= $time{idx} AND {rel}.to >= $time{idx})"
                )

            if not include_outside_parentheses:
                filters.append("\n OR ".join(filters_per_rel))

            filters.append("(" + "\n OR ".join(filters_per_rel) + ")")

        return filters, params

    def get_query_filter_path(self, at: Optional[Union[Timestamp, str]] = None) -> Tuple[str, Dict]:
        """Generate a CYPHER Query filter based on a path to query a part of the graph at a specific time and on a specific branch.

        Examples:
            >>> rels_filter, rels_params = self.branch.get_query_filter_path(at=self.at)
            >>> self.params.update(rels_params)
            >>> query += "\n WHERE all(r IN relationships(p) WHERE %s)" % rels_filter

            There is a currently an assuption that the relationship in the path will be named 'r'
        """

        at = Timestamp(at)
        branches_times = self.get_branches_and_times_to_query_global(at=at.to_string())

        params = {}
        for idx, (branch_name, time_to_query) in enumerate(branches_times.items()):
            params[f"branch{idx}"] = list(branch_name)
            params[f"time{idx}"] = time_to_query

        filters = []
        for idx, (branch_name, time_to_query) in enumerate(branches_times.items()):
            filters.append(f"(r.branch IN $branch{idx} AND r.from <= $time{idx} AND r.to IS NULL)")
            filters.append(f"(r.branch IN $branch{idx} AND r.from <= $time{idx} AND r.to >= $time{idx})")

        filter = "(" + "\n OR ".join(filters) + ")"

        return filter, params

    def get_query_filter_relationships_range(
        self,
        rel_labels: list,
        start_time: Union[Timestamp, str],
        end_time: Union[Timestamp, str],
        include_outside_parentheses: bool = False,
        include_global: bool = False,
    ) -> Tuple[List, Dict]:
        """Generate a CYPHER Query filter based on a list of relationships to query a range of values in the graph.
        The goal is to return all the values that are valid during this timerange.
        """

        filters = []
        params = {}

        if not isinstance(rel_labels, list):
            raise TypeError(f"rel_labels must be a list, not a {type(rel_labels)}")

        start_time = Timestamp(start_time)
        end_time = Timestamp(end_time)

        if include_global:
            branches_times = self.get_branches_and_times_to_query_global(at=start_time)
        else:
            branches_times = self.get_branches_and_times_to_query(at=start_time)

        params["branches"] = list({branch for branches in branches_times for branch in branches})
        params["start_time"] = start_time.to_string()
        params["end_time"] = end_time.to_string()

        for rel in rel_labels:
            filters_per_rel = [
                f"({rel}.branch IN $branches AND {rel}.from <= $end_time AND {rel}.to IS NULL)",
                f"({rel}.branch IN $branches AND ({rel}.from <= $end_time OR ({rel}.to >= $start_time AND {rel}.to <= $end_time)))",
            ]

            if not include_outside_parentheses:
                filters.append("\n OR ".join(filters_per_rel))

            filters.append("(" + "\n OR ".join(filters_per_rel) + ")")

        return filters, params

    def get_query_filter_relationships_diff(
        self,
        rel_labels: list,
        diff_from: Timestamp,
        diff_to: Timestamp,
    ) -> Tuple[List, Dict]:
        """Generate a CYPHER Query filter to query all events that are applicable to a given branch based
        - The time when the branch as created
        - The branched_from time of the branch
        - The diff_to and diff_from time as provided
        """

        if not isinstance(rel_labels, list):
            raise TypeError(f"rel_labels must be a list, not a {type(rel_labels)}")

        start_times, end_times = self.get_branches_and_times_for_range(start_time=diff_from, end_time=diff_to)

        filters = []
        params = {}

        for idx, branch_name in enumerate(start_times.keys()):
            params[f"branch{idx}"] = branch_name
            params[f"start_time{idx}"] = start_times[branch_name]
            params[f"end_time{idx}"] = end_times[branch_name]

        for rel in rel_labels:
            filters_per_rel = []
            for idx, branch_name in enumerate(start_times.keys()):
                filters_per_rel.extend(
                    [
                        f"""({rel}.branch = $branch{idx}
                             AND {rel}.from >= $start_time{idx}
                             AND {rel}.from <= $end_time{idx}
                             AND ( r2.to is NULL or r2.to >= $end_time{idx}))""",
                        f"""({rel}.branch = $branch{idx} AND {rel}.from >= $start_time{idx}
                            AND {rel}.to <= $start_time{idx})""",
                    ]
                )

            filters.append("(" + "\n OR ".join(filters_per_rel) + ")")

        return filters, params

    def get_query_filter_range(
        self,
        rel_label: list,
        start_time: Union[Timestamp, str],
        end_time: Union[Timestamp, str],
    ) -> Tuple[List, Dict]:
        """Generate a CYPHER Query filter to query a range of values in the graph between start_time and end_time."""

        filters = []
        params = {}

        start_time = Timestamp(start_time)
        end_time = Timestamp(end_time)

        params["branches"] = self.get_branches_in_scope()
        params["start_time"] = start_time.to_string()
        params["end_time"] = end_time.to_string()

        filters_per_rel = [
            f"""({rel_label}.branch IN $branches AND {rel_label}.from >= $start_time
                 AND {rel_label}.from <= $end_time AND {rel_label}.to IS NULL)""",
            f"""({rel_label}.branch IN $branches AND (({rel_label}.from >= $start_time
                 AND {rel_label}.from <= $end_time) OR ({rel_label}.to >= $start_time
                 AND {rel_label}.to <= $end_time)))""",
        ]

        filters.append("(" + "\n OR ".join(filters_per_rel) + ")")

        return filters, params

    async def rebase(self, session: AsyncSession):
        """Rebase the current Branch with its origin branch"""

        # FIXME, we must ensure that there is no conflict before rebasing a branch
        #   Otherwise we could endup with a complicated situation
        self.branched_from = Timestamp().to_string()
        await self.save(session=session)

        # Update the branch in the registry after the rebase

        registry.branch[self.name] = self

    async def validate_branch(self, rpc_client: InfrahubRpcClient, session: AsyncSession) -> Tuple[bool, List[str]]:
        """Validate if a branch is eligible to be merged.
        - Must be conflict free both for data and repository
        - All checks must pass
        - Check schema changes

        Need to support with and without rebase

        Need to return a list of violations, must be multiple
        """

        graph_passed, graph_messages = await self.validate_graph(session=session)
        repo_passed, repo_messages = await self.validate_repositories(rpc_client=rpc_client, session=session)

        messages = graph_messages + repo_messages
        passed = graph_passed & repo_passed

        return passed, messages

    async def validate_graph(self, session: AsyncSession) -> Tuple[bool, List[str]]:
        passed = True
        messages = []

        # Check the diff and ensure the branch doesn't have some conflict
        diff = await self.diff(session=session)
        if conflicts := await diff.get_conflicts(session=session):
            passed = False
            for conflict in conflicts:
                messages.append(f"Conflict detected at {conflict}")

        return passed, messages

    async def validate_repositories(
        self, rpc_client: InfrahubRpcClient, session: AsyncSession
    ) -> Tuple[bool, List[str]]:
        passed = True
        messages = []
        tasks = []

        # For all repositories in this branch, run all checks
        repos = await NodeManager.query(schema="CoreRepository", branch=self, session=session)

        # Collecting all the checks from all the repopository
        for repo in repos:
            for rel_check in await repo.checks.get(session=session):
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
        branch_only: bool = False,
        diff_from: Optional[Union[str, Timestamp]] = None,
        diff_to: Optional[Union[str, Timestamp]] = None,
        session: Optional[AsyncSession] = None,
    ) -> Diff:
        return await Diff.init(
            branch=self, diff_from=diff_from, diff_to=diff_to, branch_only=branch_only, session=session
        )

    async def merge(
        self, rpc_client: InfrahubRpcClient, at: Union[str, Timestamp] = None, session: Optional[AsyncSession] = None
    ):
        """Merge the current branch into main."""

        passed, _ = await self.validate_branch(rpc_client=rpc_client, session=session)
        if not passed:
            raise ValidationError(f"Unable to merge the branch '{self.name}', validation failed")

        if self.name == config.SETTINGS.main.default_branch:
            raise ValidationError(f"Unable to merge the branch '{self.name}' into itself")

        # TODO need to find a way to properly communicate back to the user any issue that could come up during the merge
        # From the Graph or From the repositories
        await self.merge_graph(session=session, at=at)

        await self.merge_repositories(rpc_client=rpc_client, session=session)

    async def merge_graph(self, session: AsyncSession, at: Optional[Union[str, Timestamp]] = None):
        rel_ids_to_update = []

        default_branch: Branch = registry.branch[config.SETTINGS.main.default_branch]

        at = Timestamp(at)

        diff = await Diff.init(branch=self, session=session)
        nodes = await diff.get_nodes(session=session)

        if self.name in nodes:
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
                if node.action == DiffAction.ADDED:
                    query = await AddNodeToBranch.init(session=session, node_id=node.db_id, branch=default_branch)
                    await query.execute(session=session)
                    rel_ids_to_update.append(node.rel_id)

                elif node.action == DiffAction.REMOVED:
                    query = await NodeDeleteQuery.init(session=session, branch=default_branch, node_id=node_id, at=at)
                    await query.execute(session=session)
                    rel_ids_to_update.extend([node.rel_id, origin_nodes[node_id].get("rb").element_id])

                for _, attr in node.attributes.items():
                    if attr.action == DiffAction.ADDED:
                        await add_relationship(
                            src_node_id=node.db_id,
                            dst_node_id=attr.db_id,
                            rel_type="HAS_ATTRIBUTE",
                            at=at,
                            branch_name=default_branch.name,
                            branch_level=default_branch.hierarchy_level,
                            session=session,
                        )
                        rel_ids_to_update.append(attr.rel_id)

                    elif attr.action == DiffAction.REMOVED:
                        await add_relationship(
                            src_node_id=node.db_id,
                            dst_node_id=attr.db_id,
                            rel_type="HAS_ATTRIBUTE",
                            branch_name=default_branch.name,
                            branch_level=default_branch.hierarchy_level,
                            at=at,
                            status=RelationshipStatus.DELETED,
                            session=session,
                        )
                        rel_ids_to_update.extend([attr.rel_id, attr.origin_rel_id])

                    for prop_type, prop in attr.properties.items():
                        if prop.action == DiffAction.ADDED:
                            await add_relationship(
                                src_node_id=attr.db_id,
                                dst_node_id=prop.db_id,
                                rel_type=prop_type,
                                at=at,
                                branch_name=default_branch.name,
                                branch_level=default_branch.hierarchy_level,
                                session=session,
                            )
                            rel_ids_to_update.append(prop.rel_id)

                        elif prop.action == DiffAction.UPDATED:
                            await add_relationship(
                                src_node_id=attr.db_id,
                                dst_node_id=prop.db_id,
                                rel_type=prop_type,
                                at=at,
                                branch_name=default_branch.name,
                                branch_level=default_branch.hierarchy_level,
                                session=session,
                            )
                            rel_ids_to_update.extend([prop.rel_id, prop.origin_rel_id])

                        elif prop.action == DiffAction.REMOVED:
                            await add_relationship(
                                src_node_id=attr.db_id,
                                dst_node_id=prop.db_id,
                                rel_type=prop_type,
                                at=at,
                                branch_name=default_branch.name,
                                branch_level=default_branch.hierarchy_level,
                                status=RelationshipStatus.DELETED,
                                session=session,
                            )
                            rel_ids_to_update.extend([prop.rel_id, prop.origin_rel_id])

        # ---------------------------------------------
        # RELATIONSHIPS
        # ---------------------------------------------
        rels = await diff.get_relationships(session=session)

        for rel_name in rels[self.name].keys():
            for _, rel in rels[self.name][rel_name].items():
                for node in rel.nodes.values():
                    if rel.action in [DiffAction.ADDED, DiffAction.REMOVED]:
                        rel_status = RelationshipStatus.ACTIVE
                        if rel.action == DiffAction.REMOVED:
                            rel_status = RelationshipStatus.DELETED

                        await add_relationship(
                            src_node_id=node.db_id,
                            dst_node_id=rel.db_id,
                            rel_type="IS_RELATED",
                            at=at,
                            branch_name=default_branch.name,
                            branch_level=default_branch.hierarchy_level,
                            status=rel_status,
                            session=session,
                        )
                        rel_ids_to_update.append(node.rel_id)

                for prop_type, prop in rel.properties.items():
                    rel_status = RelationshipStatus.ACTIVE
                    if prop.action == DiffAction.REMOVED:
                        rel_status = RelationshipStatus.DELETED

                    await add_relationship(
                        src_node_id=rel.db_id,
                        dst_node_id=prop.db_id,
                        rel_type=prop.type,
                        at=at,
                        branch_name=default_branch.name,
                        branch_level=default_branch.hierarchy_level,
                        session=session,
                    )
                    rel_ids_to_update.append(prop.rel_id)

                    if rel.action in [DiffAction.UPDATED, DiffAction.REMOVED]:
                        rel_ids_to_update.append(prop.origin_rel_id)

        await update_relationships_to(ids=rel_ids_to_update, to=at, session=session)

        await self.rebase(session=session)

    async def merge_repositories(self, rpc_client: InfrahubRpcClient, session: AsyncSession):
        # Collect all Repositories in Main because we'll need the commit in Main for each one.
        repos_in_main_list = await NodeManager.query(schema="CoreRepository", session=session)
        repos_in_main = {repo.id: repo for repo in repos_in_main_list}
        tasks = []

        repos_in_branch_list = await NodeManager.query(schema="CoreRepository", session=session, branch=self)

        for repo in repos_in_branch_list:
            # Check if the repo, exist in main, if not ignore this repo
            if repo.id not in repos_in_main:
                continue

            # repos_in_main[repo.id]
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


class BaseDiffElement(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    def to_graphql(self):
        """Recursively Export the model to a dict for GraphQL.
        The main rules of convertion are:
            - Ignore the fields mark as exclude=True
            - Convert the Dict in List
        """
        resp = {}
        for key, value in self:
            if isinstance(value, BaseModel):
                resp[key] = value.to_graphql()
            elif isinstance(value, dict):
                resp[key] = [item.to_graphql() for item in value.values()]
            elif self.__fields__[key].field_info.exclude:
                continue
            elif isinstance(value, Enum):
                resp[key] = value.value
            elif isinstance(value, Timestamp):
                resp[key] = value.to_string()
            else:
                resp[key] = value

        return resp


class ValueElement(BaseDiffElement):
    previous: Optional[Any]
    new: Optional[Any]


class PropertyDiffElement(BaseDiffElement):
    branch: str
    type: str
    action: DiffAction
    db_id: str = Field(exclude=True)
    rel_id: str = Field(exclude=True)
    origin_rel_id: Optional[str] = Field(exclude=True)
    value: Optional[ValueElement]
    changed_at: Optional[Timestamp]


class NodeAttributeDiffElement(BaseDiffElement):
    id: str
    name: str
    action: DiffAction
    db_id: str = Field(exclude=True)
    rel_id: str = Field(exclude=True)
    origin_rel_id: Optional[str] = Field(exclude=True)
    changed_at: Optional[Timestamp]
    properties: Dict[str, PropertyDiffElement]


class NodeDiffElement(BaseDiffElement):
    branch: Optional[str]
    labels: List[str]
    kind: str
    id: str
    action: DiffAction
    db_id: str = Field(exclude=True)
    rel_id: Optional[str] = Field(exclude=True)
    changed_at: Optional[Timestamp]
    attributes: Dict[str, NodeAttributeDiffElement]


class RelationshipEdgeNodeDiffElement(BaseDiffElement):
    id: str
    db_id: Optional[str] = Field(exclude=True)
    rel_id: Optional[str] = Field(exclude=True)
    labels: List[str]
    kind: str


class RelationshipDiffElement(BaseDiffElement):
    branch: Optional[str]
    id: str
    db_id: str = Field(exclude=True)
    name: str
    action: DiffAction
    nodes: Dict[str, RelationshipEdgeNodeDiffElement]
    properties: Dict[str, PropertyDiffElement]
    changed_at: Optional[Timestamp]


class FileDiffElement(BaseDiffElement):
    branch: str
    location: str
    repository: str
    action: DiffAction
    commit_from: str
    commit_to: str

    def __hash__(self):
        return hash((type(self),) + tuple(self.__dict__.values()))


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
        """_summary_

        Args:
            branch (Branch): Main branch this diff is caculated from
            origin_branch (Branch): Storing the origin branch the main branch started from for convenience.
            branch_only (bool, optional): When True, only consider the changes in the branch, ignore the changes in main. Defaults to False.
            diff_from (Union[str, Timestamp], optional): Time from when the diff is calculated. Defaults to None.
            diff_to (Union[str, Timestamp], optional): Time to when the diff is calculated. Defaults to None.

        Raises:
            ValueError: if diff_from and diff_to are not correct
        """

        self.branch = branch
        self.branch_only = branch_only
        self.origin_branch = origin_branch

        if not diff_from and self.branch.is_default:
            raise ValueError(f"diff_from is mandatory when diffing on the default branch `{self.branch.name}`.")

        # If diff from hasn't been provided, we'll use the creation of the branch as the starting point
        if diff_from:
            self.diff_from = Timestamp(diff_from)
        else:
            self.diff_from = Timestamp(self.branch.created_at)

        # If diff_to hasn't been provided, we will use the current time.
        self.diff_to = Timestamp(diff_to)

        if self.diff_to < self.diff_from:
            raise ValueError("diff_to must be later than diff_from")

        # Results organized by Branch
        self._results: Dict[str, dict] = defaultdict(
            lambda: {"nodes": {}, "rels": defaultdict(lambda: {}), "files": {}}
        )

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

    async def has_conflict(
        self, session: AsyncSession, rpc_client: InfrahubRpcClient  # pylint: disable=unused-argument
    ) -> bool:
        """Return True if the same path has been modified on multiple branches. False otherwise"""

        return await self.has_conflict_graph(session=session)

    async def has_conflict_graph(self, session: AsyncSession) -> bool:
        """Return True if the same path has been modified on multiple branches. False otherwise"""

        if await self.get_conflicts_graph(session=session):
            return True

        return False

    async def has_changes(self, session: AsyncSession, rpc_client: InfrahubRpcClient) -> bool:
        """Return True if the diff has identified some changes, False otherwise."""

        has_changes_graph = await self.has_changes_graph(session=session)
        has_changes_repositories = await self.has_changes_repositories(session=session, rpc_client=rpc_client)

        return has_changes_graph | has_changes_repositories

    async def has_changes_graph(self, session: AsyncSession) -> bool:
        """Return True if the diff has identified some changes in the Graph, False otherwise."""

        mpaths = await self.get_modified_paths_graph(session=session)
        for _, paths in mpaths.items():
            if paths:
                return True

        return False

    async def has_changes_repositories(self, session: AsyncSession, rpc_client: InfrahubRpcClient) -> bool:
        """Return True if the diff has identified some changes in the repositories, False otherwise."""

        mpaths = await self.get_modified_paths_repositories(session=session, rpc_client=rpc_client)
        for _, paths in mpaths.items():
            if paths:
                return True

        return False

    async def get_conflicts(self, session: AsyncSession) -> List[ObjectConflict]:
        """Return the list of conflicts identified by the diff as Path (tuple).

        For now we are not able to identify clearly enough the conflicts for the git repositories so this part is ignored.
        """
        return await self.get_conflicts_graph(session=session)

    async def get_conflicts_graph(self, session: AsyncSession) -> List[ObjectConflict]:
        if self.branch_only:
            return []

        paths = await self.get_modified_paths_graph(session=session)

        # For now we assume that we can only have 2 branches but in the future we might need to support more
        branches = list(paths.keys())

        # if we don't have at least 2 branches returned we can safely assumed there is no conflict
        if len(branches) < 2:
            return []

        # Since we have 2 sets or tuple, we can quickly calculate the intersection using set(A) & set(B)
        conflicts = paths[branches[0]] & paths[branches[1]]

        return [ObjectConflict(type=conflict.type, id=conflict.node_id, path=str(conflict)) for conflict in conflicts]

    async def get_modified_paths_graph(self, session: AsyncSession) -> Dict[str, Set[ModifiedPath]]:
        """Return a list of all the modified paths in the graph per branch.

        Path for a node : ("node", node_id, attr_name, prop_type)
        Path for a relationship : ("relationships", rel_name, rel_id, prop_type

        Returns:
            Dict[str, set]: Returns a dictionnary by branch with a set of paths
        """

        paths = {}

        nodes = await self.get_nodes(session=session)
        for branch_name, data in nodes.items():
            if self.branch_only and branch_name != self.branch.name:
                continue

            if branch_name not in paths:
                paths[branch_name] = set()

            for node_id, node in data.items():
                p = ModifiedPath(type="data", node_id=node_id, action=node.action)
                paths[branch_name].add(p)
                for attr_name, attr in node.attributes.items():
                    for prop_type in attr.properties.keys():
                        p = ModifiedPath(
                            type="data",
                            node_id=node_id,
                            action=attr.action,
                            element_name=attr_name,
                            property_name=prop_type,
                        )
                        paths[branch_name].add(p)

        relationships = await self.get_relationships(session=session)
        for branch_name, data in relationships.items():  # pylint: disable=too-many-nested-blocks
            if self.branch_only and branch_name != self.branch.name:
                continue

            if branch_name not in paths:
                paths[branch_name] = set()

            for rel_name, rels in data.items():
                for _, rel in rels.items():
                    for prop_type in rel.properties.keys():
                        for node_id in rel.nodes:
                            neighbor_id = [neighbor for neighbor in rel.nodes.keys() if neighbor != node_id][0]
                            schema = registry.get_schema(name=rel.nodes[node_id].kind, branch=branch_name)
                            matching_relationship = [r for r in schema.relationships if r.identifier == rel_name]
                            if matching_relationship:
                                p = ModifiedPath(
                                    type="data",
                                    node_id=node_id,
                                    action=rel.action,
                                    element_name=matching_relationship[0].name,
                                    property_name=prop_type,
                                    peer_id=neighbor_id,
                                )
                                paths[branch_name].add(p)

        return paths

    async def get_modified_paths_repositories(
        self, session: AsyncSession, rpc_client: InfrahubRpcClient
    ) -> Dict[str, Set[Tuple]]:
        """Return a list of all the modified paths in the repositories.

        We need the commit values for each repository in the graph to calculate the difference.

        For now we are still assuming that a Branch always start from main
        """

        paths = defaultdict(set)

        for branch, items in await self.get_files_repositories_for_branch(
            session=session, rpc_client=rpc_client, branch=self.branch
        ):
            for item in items:
                paths[branch] = ("file", item.repository, item.location)

        if not self.branch_only:
            for branch, items in await self.get_modified_paths_repositories_for_branch(
                session=session, rpc_client=rpc_client, branch=self.origin_branch
            ):
                for item in items:
                    paths[branch] = ("file", item.repository, item.location)

        return paths

    async def get_modified_paths_repositories_for_branch(
        self, session: AsyncSession, rpc_client: InfrahubRpcClient, branch: Branch
    ) -> Set[Tuple]:
        tasks = []
        paths = set()

        repos_to = {
            repo.id: repo
            for repo in await NodeManager.query(schema="Repository", session=session, branch=branch, at=self.diff_to)
        }
        repos_from = {
            repo.id: repo
            for repo in await NodeManager.query(schema="Repository", session=session, branch=branch, at=self.diff_from)
        }

        # For now we are ignoring the repos that are either not present at to time or at from time.
        # These repos will be identified in the graph already
        repo_ids_common = set(repos_to.keys()) & set(repos_from.keys())

        for repo_id in repo_ids_common:
            if repos_to[repo_id].commit.value == repos_from[repo_id].commit.value:
                continue

            tasks.append(
                self.get_modified_paths_repository(
                    rpc_client=rpc_client,
                    repository=repos_to[repo_id],
                    commit_from=repos_from[repo_id].commit.value,
                    commit_to=repos_to[repo_id].commit.value,
                )
            )

        responses = await asyncio.gather(*tasks)

        for response in responses:
            paths.update(response)

        return paths

    async def get_modified_paths_repository(
        self, rpc_client: InfrahubRpcClient, repository, commit_from: str, commit_to: str
    ) -> Set[Tuple]:
        """Return the path of all the files that have changed for a given repository between 2 commits.

        Path format: ("file", repository.id, filename )
        """

        response: InfrahubRPCResponse = await rpc_client.call(
            message=InfrahubGitRPC(
                action=GitMessageAction.DIFF,
                repository=repository,
                params={"first_commit": commit_from, "second_commit": commit_to},
            )
        )

        return {("file", repository.id, filename) for filename in response.response.get("files_changed", [])}

    async def get_nodes(self, session: AsyncSession) -> Dict[str, Dict[str, NodeDiffElement]]:
        """Return all the nodes calculated by the diff, organized by branch."""

        if not self._calculated_diff_nodes_at:
            await self._calculate_diff_nodes(session=session)

        return {
            branch_name: data["nodes"]
            for branch_name, data in self._results.items()
            if not self.branch_only or branch_name == self.branch.name
        }

    async def _calculate_diff_nodes(self, session: AsyncSession):
        """Calculate the diff for all the nodes and attributes.

        The results will be stored in self._results organized by branch.
        """
        # ------------------------------------------------------------
        # Process nodes that have been Added or Removed first
        # ------------------------------------------------------------
        query_nodes = await DiffNodeQuery.init(
            session=session, branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to
        )
        await query_nodes.execute(session=session)

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
            branch_name = result.get("r").get("branch")
            from_time = result.get("r").get("from")

            item = {
                "branch": result.get("r").get("branch"),
                "labels": sorted(list(result.get("n").labels)),
                "kind": result.get("n").get("kind"),
                "id": node_id,
                "db_id": result.get("n").element_id,
                "attributes": {},
                "rel_id": result.get("r").element_id,
                "changed_at": Timestamp(from_time),
            }

            if branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED
            elif branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED

            self._results[branch_name]["nodes"][node_id] = NodeDiffElement(**item)

        # ------------------------------------------------------------
        # Process Attributes that have been Added, Updated or Removed
        #  We don't process the properties right away, instead we'll identify the node that mostlikely already exist
        #  and we'll query the current value to fully understand what we need to do with it.
        # ------------------------------------------------------------
        attrs_to_query = set()
        query_attrs = await DiffAttributeQuery.init(
            session=session, branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to
        )
        await query_attrs.execute(session=session)

        for result in query_attrs.get_results():
            node_id = result.get("n").get("uuid")
            branch_name = result.get("r2").get("branch")

            # Check if the node already exist, if not it means it was not added or removed so it was updated
            if node_id not in self._results[branch_name]["nodes"].keys():
                item = {
                    "labels": sorted(list(result.get("n").labels)),
                    "kind": result.get("n").get("kind"),
                    "id": node_id,
                    "db_id": result.get("n").element_id,
                    "attributes": {},
                    "changed_at": None,
                    "action": DiffAction.UPDATED,
                    "rel_id": None,
                    "branch": branch_name,
                }

                self._results[branch_name]["nodes"][node_id] = NodeDiffElement(**item)

            # Check if the Attribute is already present or if it was added during this time frame.
            attr_name = result.get("a").get("name")
            attr_id = result.get("a").get("uuid")
            if attr_name not in self._results[branch_name]["nodes"][node_id].attributes.keys():
                node = self._results[branch_name]["nodes"][node_id]
                item = {
                    "id": attr_id,
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
                    node.action == DiffAction.ADDED
                    and attr_from >= self.diff_from
                    and branch_status == RelationshipStatus.ACTIVE.value
                ):
                    item["action"] = DiffAction.ADDED
                    item["changed_at"] = attr_from

                elif attr_from >= self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                    item["action"] = DiffAction.REMOVED
                    item["changed_at"] = attr_from

                    attrs_to_query.add(attr_id)
                else:
                    item["action"] = DiffAction.UPDATED
                    item["changed_at"] = None

                    attrs_to_query.add(attr_id)

                self._results[branch_name]["nodes"][node_id].attributes[attr_name] = NodeAttributeDiffElement(**item)

        # ------------------------------------------------------------
        # Query the current value for all attributes that have been updated
        # ------------------------------------------------------------
        origin_attr_query = await DiffNodePropertiesByIDSQuery.init(
            session=session,
            ids=list(attrs_to_query),
            branch=self.branch,
            at=self.diff_from,
        )

        await origin_attr_query.execute(session=session)

        for result in query_attrs.get_results():
            node_id = result.get("n").get("uuid")
            branch_name = result.get("r2").get("branch")
            branch_status = result.get("r2").get("status")
            attr_id = result.get("a").get("uuid")
            attr_name = result.get("a").get("name")
            prop_type = result.get("r2").type

            origin_attr = origin_attr_query.get_results_by_id_and_prop_type(attr_id=attr_id, prop_type=prop_type)

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
                "value": {"new": result.get("ap").get("value"), "previous": None},
            }

            if origin_attr:
                item["origin_rel_id"] = origin_attr[0].get("r").element_id
                item["value"]["previous"] = origin_attr[0].get("ap").get("value")

            if not origin_attr and prop_from >= self.diff_from and branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED
                item["changed_at"] = prop_from
            elif prop_from >= self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED
                item["changed_at"] = prop_from
            else:
                item["action"] = DiffAction.UPDATED
                item["changed_at"] = prop_from

            self._results[branch_name]["nodes"][node_id].attributes[attr_name].origin_rel_id = result.get(
                "r1"
            ).element_id
            self._results[branch_name]["nodes"][node_id].attributes[attr_name].properties[
                prop_type
            ] = PropertyDiffElement(**item)

        self._calculated_diff_nodes_at = Timestamp()

    async def get_relationships(
        self, session: AsyncSession
    ) -> Dict[str, Dict[str, Dict[str, RelationshipDiffElement]]]:
        if not self._calculated_diff_rels_at:
            await self._calculated_diff_rels(session=session)

        return {
            branch_name: data["rels"]
            for branch_name, data in self._results.items()
            if not self.branch_only or branch_name == self.branch.name
        }

    async def get_relationships_per_node(
        self, session: AsyncSession
    ) -> Dict[str, Dict[str, Dict[str, List[RelationshipDiffElement]]]]:
        rels = await self.get_relationships(session=session)

        # Organize the Relationships data per node and per relationship name in order to simplify the association with the nodes Later on.
        rels_per_node: Dict[str, Dict[str, Dict[str, List[RelationshipDiffElement]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        for branch_name, items in rels.items():
            for item in items.values():
                for sub_item in item.values():
                    for node_id, _ in sub_item.nodes.items():
                        rels_per_node[branch_name][node_id][sub_item.name].append(sub_item)

        return rels_per_node

    async def get_node_id_per_kind(self, session: AsyncSession) -> Dict[str, Dict[str, List[str]]]:
        # Node IDs organized per Branch and per Kind
        rels = await self.get_relationships(session=session)
        nodes = await self.get_nodes(session=session)

        node_ids: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

        for branch_name, items in rels.items():
            for item in items.values():
                for sub_item in item.values():
                    for node_id, node in sub_item.nodes.items():
                        if node_id not in node_ids[branch_name][node.kind]:
                            node_ids[branch_name][node.kind].append(node_id)

        # Extract the id of all nodes ahead of time in order to query all display labels
        for branch_name, items in nodes.items():
            for item in items.values():
                if item.id not in node_ids[branch_name][item.kind]:
                    node_ids[branch_name][item.kind].append(item.id)

        return node_ids

    async def _calculated_diff_rels(self, session: AsyncSession):
        """Calculate the diff for all the relationships between Nodes.

        The results will be stored in self._results organized by branch.
        """

        rel_ids_to_query = []

        # ------------------------------------------------------------
        # Process first the main path of the relationships
        #   to identify the relationship that have been ADDED or DELETED
        # ------------------------------------------------------------
        query_rels = await DiffRelationshipQuery.init(
            session=session, branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to
        )
        await query_rels.execute(session=session)

        for result in query_rels.get_results():
            branch_name = result.get("r1").get("branch")
            branch_status = result.get("r1").get("status")
            rel_name = result.get("rel").get("name")
            rel_id = result.get("rel").get("uuid")

            src_node_id = result.get("sn").get("uuid")
            dst_node_id = result.get("dn").get("uuid")

            from_time = Timestamp(result.get("r1").get("from"))
            # to_time = result.get("r1").get("to", None)

            item = {
                "branch": branch_name,
                "id": rel_id,
                "db_id": result.get("rel").element_id,
                "name": rel_name,
                "nodes": {
                    src_node_id: RelationshipEdgeNodeDiffElement(
                        id=src_node_id,
                        db_id=result.get("sn").element_id,
                        rel_id=result.get("r1").element_id,
                        labels=sorted(result.get("sn").labels),
                        kind=result.get("sn").get("kind"),
                    ),
                    dst_node_id: RelationshipEdgeNodeDiffElement(
                        id=dst_node_id,
                        db_id=result.get("dn").element_id,
                        rel_id=result.get("r2").element_id,
                        labels=sorted(result.get("dn").labels),
                        kind=result.get("dn").get("kind"),
                    ),
                },
                "properties": {},
            }

            # FIXME Need to revisit changed_at, mostlikely not accurate. More of a placeholder at this point
            if branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED
                item["changed_at"] = from_time
            elif branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED
                item["changed_at"] = from_time
                rel_ids_to_query.append(rel_id)
            else:
                raise ValueError(f"Unexpected value for branch_status: {branch_status}")

            self._results[branch_name]["rels"][rel_name][rel_id] = RelationshipDiffElement(**item)

        # ------------------------------------------------------------
        # Then Query & Process the properties of the relationships
        #  First we need to need to create the RelationshipDiffElement that haven't been created previously
        #  Then we can process the properties themselves
        # ------------------------------------------------------------
        query_props = await DiffRelationshipPropertyQuery.init(
            session=session, branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to
        )
        await query_props.execute(session=session)

        for result in query_props.get_results():
            branch_name = result.get("r3").get("branch")
            branch_status = result.get("r3").get("status")
            rel_name = result.get("rel").get("name")
            rel_id = result.get("rel").get("uuid")

            # Check if the relationship already exist, if not we need to create it
            if rel_id in self._results[branch_name]["rels"][rel_name]:
                continue

            src_node_id = result.get("sn").get("uuid")
            dst_node_id = result.get("dn").get("uuid")

            item = {
                "id": rel_id,
                "db_id": result.get("rel").element_id,
                "name": rel_name,
                "nodes": {
                    src_node_id: RelationshipEdgeNodeDiffElement(
                        id=src_node_id,
                        db_id=result.get("sn").element_id,
                        rel_id=result.get("r1").element_id,
                        kind=result.get("sn").get("kind"),
                        labels=sorted(result.get("sn").labels),
                    ),
                    dst_node_id: RelationshipEdgeNodeDiffElement(
                        id=dst_node_id,
                        db_id=result.get("dn").element_id,
                        rel_id=result.get("r2").element_id,
                        kind=result.get("dn").get("kind"),
                        labels=sorted(result.get("dn").labels),
                    ),
                },
                "properties": {},
                "action": DiffAction.UPDATED,
                "changed_at": None,
                "branch": branch_name,
            }

            self._results[branch_name]["rels"][rel_name][rel_id] = RelationshipDiffElement(**item)

            rel_ids_to_query.append(rel_id)

        # ------------------------------------------------------------
        # Query the current value of the relationships that have been flagged
        #  Usually we need more information to determine if the rel has been updated, added or removed
        # ------------------------------------------------------------
        origin_rel_properties_query = await DiffRelationshipPropertiesByIDSRangeQuery.init(
            session=session,
            ids=rel_ids_to_query,
            branch=self.branch,
            diff_from=self.diff_from,
            diff_to=self.diff_to,
        )
        await origin_rel_properties_query.execute(session=session)

        for result in query_props.get_results():
            branch_name = result.get("r3").get("branch")
            branch_status = result.get("r3").get("status")
            rel_name = result.get("rel").get("name")
            rel_id = result.get("rel").get("uuid")

            prop_type = result.get("r3").type
            prop_from = Timestamp(result.get("r3").get("from"))

            origin_prop = origin_rel_properties_query.get_results_by_id_and_prop_type(
                rel_id=rel_id, prop_type=prop_type
            )

            prop = {
                "type": prop_type,
                "branch": branch_name,
                "db_id": result.get("rp").element_id,
                "rel_id": result.get("r3").element_id,
                "origin_rel_id": None,
                "value": {"new": result.get("rp").get("value"), "previous": None},
            }

            if origin_prop:
                prop["origin_rel_id"] = origin_prop[0].get("r").element_id
                prop["value"]["previous"] = origin_prop[0].get("rp").get("value")

            if not origin_prop and prop_from >= self.diff_from and branch_status == RelationshipStatus.ACTIVE.value:
                prop["action"] = DiffAction.ADDED
                prop["changed_at"] = prop_from
            elif prop_from >= self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                prop["action"] = DiffAction.REMOVED
                prop["changed_at"] = prop_from
            else:
                prop["action"] = DiffAction.UPDATED
                prop["changed_at"] = prop_from

            self._results[branch_name]["rels"][rel_name][rel_id].properties[prop_type] = PropertyDiffElement(**prop)

        self._calculated_diff_rels_at = Timestamp()

    async def get_files(self, session: AsyncSession, rpc_client: InfrahubRpcClient) -> Dict[str, List[FileDiffElement]]:
        if not self._calculated_diff_files_at:
            await self._calculated_diff_files(session=session, rpc_client=rpc_client)

        return {
            branch_name: data["files"]
            for branch_name, data in self._results.items()
            if not self.branch_only or branch_name == self.branch.name
        }

    async def _calculated_diff_files(self, session: AsyncSession, rpc_client: InfrahubRpcClient):
        self._results[self.branch.name]["files"] = await self.get_files_repositories_for_branch(
            session=session, rpc_client=rpc_client, branch=self.branch
        )

        if self.origin_branch:
            self._results[self.origin_branch.name]["files"] = await self.get_files_repositories_for_branch(
                session=session, rpc_client=rpc_client, branch=self.origin_branch
            )

        self._calculated_diff_files_at = Timestamp()

    async def get_files_repository(
        self,
        rpc_client: InfrahubRpcClient,
        branch_name: str,
        repository,
        commit_from: str,
        commit_to: str,
    ) -> List[FileDiffElement]:
        """Return all the files that have added, changed or removed for a given repository between 2 commits."""

        files = []

        response: InfrahubRPCResponse = await rpc_client.call(
            message=InfrahubGitRPC(
                action=GitMessageAction.DIFF,
                repository=repository,
                params={"first_commit": commit_from, "second_commit": commit_to},
            )
        )

        actions = {
            "files_changed": DiffAction.UPDATED,
            "files_added": DiffAction.ADDED,
            "files_removed": DiffAction.REMOVED,
        }

        for action_name, diff_action in actions.items():
            for filename in response.response.get(action_name, []):
                files.append(
                    FileDiffElement(
                        branch=branch_name,
                        location=filename,
                        repository=repository.id,
                        action=diff_action,
                        commit_to=commit_to,
                        commit_from=commit_from,
                    )
                )

        return files

    async def get_files_repositories_for_branch(
        self, session: AsyncSession, rpc_client: InfrahubRpcClient, branch: Branch
    ) -> List[FileDiffElement]:
        tasks = []
        files = []

        repos_to = {
            repo.id: repo
            for repo in await NodeManager.query(
                schema="CoreRepository", session=session, branch=branch, at=self.diff_to
            )
        }
        repos_from = {
            repo.id: repo
            for repo in await NodeManager.query(
                schema="CoreRepository", session=session, branch=branch, at=self.diff_from
            )
        }

        # For now we are ignoring the repos that are either not present at to time or at from time.
        # These repos will be identified in the graph already
        repo_ids_common = set(repos_to.keys()) & set(repos_from.keys())

        for repo_id in repo_ids_common:
            if repos_to[repo_id].commit.value == repos_from[repo_id].commit.value:
                continue

            tasks.append(
                self.get_files_repository(
                    rpc_client=rpc_client,
                    branch_name=branch.name,
                    repository=repos_to[repo_id],
                    commit_from=repos_from[repo_id].commit.value,
                    commit_to=repos_to[repo_id].commit.value,
                )
            )

        responses = await asyncio.gather(*tasks)

        for response in responses:
            if isinstance(response, list):
                files.extend(response)

        return files


registry.branch_object = Branch
