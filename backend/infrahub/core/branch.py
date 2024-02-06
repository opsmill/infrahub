from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import Field as FieldV2
from pydantic import field_validator
from pydantic.v1 import BaseModel, Field

from infrahub import config
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
    BranchSupportType,
    DiffAction,
    InfrahubKind,
    PathType,
    RelationshipCardinality,
    RelationshipStatus,
)
from infrahub.core.manager import NodeManager
from infrahub.core.models import SchemaBranchHash  # noqa: TCH001
from infrahub.core.node.standard import StandardNode
from infrahub.core.query.branch import (
    AddNodeToBranch,
    DeleteBranchRelationshipsQuery,
    GetAllBranchInternalRelationshipQuery,
    RebaseBranchDeleteRelationshipQuery,
    RebaseBranchUpdateRelationshipQuery,
)
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
from infrahub.core.utils import add_relationship, update_relationships_to
from infrahub.exceptions import (
    BranchNotFound,
    DiffFromRequiredOnDefaultBranchError,
    DiffRangeValidationError,
    ValidationError,
)
from infrahub.message_bus import messages
from infrahub.message_bus.responses import DiffNamesResponse
from infrahub.services import services

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.message_bus.rpc import InfrahubRpcClient

# pylint: disable=redefined-builtin,too-many-statements,too-many-lines,too-many-branches,too-many-public-methods


class Branch(StandardNode):
    name: str = FieldV2(
        max_length=32, min_length=3, description="Name of the branch (git ref standard)", validate_default=True
    )
    status: str = "OPEN"  # OPEN, CLOSED
    description: str = ""
    origin_branch: str = "main"
    branched_from: Optional[str] = FieldV2(default=None, validate_default=True)
    hierarchy_level: int = 2
    created_at: Optional[str] = FieldV2(default=None, validate_default=True)
    is_default: bool = False
    is_global: bool = False
    is_protected: bool = False
    is_data_only: bool = False
    schema_changed_at: Optional[str] = None
    schema_hash: Optional[SchemaBranchHash] = None

    ephemeral_rebase: bool = False

    _exclude_attrs: List[str] = ["id", "uuid", "owner", "ephemeral_rebase"]

    @field_validator("name", mode="before")
    @classmethod
    def validate_branch_name(cls, value):
        checks = [
            (r".*/\.", "/."),
            (r"\.\.", ".."),
            (r"^/", "starts with /"),
            (r"//", "//"),
            (r"@{", "@{"),
            (r"\\", "backslash (\\)"),
            (r"[\000-\037\177 ~^:?*[]", "disallowed ASCII characters/patterns"),
            (r"\.lock$", "ends with .lock"),
            (r"/$", "ends with /"),
            (r"\.$", "ends with ."),
        ]

        offending_patterns = []

        for pattern, description in checks:
            if re.search(pattern, value):
                offending_patterns.append(description)

        if value == GLOBAL_BRANCH_NAME:
            return value  # this is the only allowed exception

        if offending_patterns:
            error_text = ", ".join(offending_patterns)
            raise ValidationError(f"Branch name contains invalid patterns or characters: {error_text}")

        return value

    @field_validator("branched_from", mode="before")
    @classmethod
    def set_branched_from(cls, value):
        return Timestamp(value).to_string()

    @field_validator("created_at", mode="before")
    @classmethod
    def set_created_at(cls, value):
        return Timestamp(value).to_string()

    def update_schema_hash(self, at: Optional[Union[Timestamp, str]] = None) -> bool:
        latest_schema = registry.schema.get_schema_branch(name=self.name)
        self.schema_changed_at = Timestamp(at).to_string()
        new_hash = latest_schema.get_hash_full()
        if self.schema_hash and new_hash.main == self.schema_hash.main:
            return False

        self.schema_hash = new_hash
        return True

    @classmethod
    async def get_by_name(cls, name: str, db: InfrahubDatabase) -> Branch:
        query = """
        MATCH (n:Branch)
        WHERE n.name = $name
        RETURN n
        """

        params = {"name": name}

        results = await db.execute_query(query=query, params=params, name="branch_get_by_name")

        if len(results) == 0:
            raise BranchNotFound(identifier=name)

        return cls.from_db(results[0].values()[0])

    @classmethod
    def isinstance(cls, obj: Any) -> bool:
        return isinstance(obj, cls)

    async def get_origin_branch(self, db: InfrahubDatabase) -> Optional[Branch]:
        """Return the branch Object of the origin_branch."""
        if not self.origin_branch or self.origin_branch == self.name:
            return None

        return await get_branch(branch=self.origin_branch, db=db)

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
        self,
        at: Optional[Union[Timestamp, str]] = None,
        is_isolated: bool = True,
    ) -> Dict[frozenset, str]:
        """Return all the names of the branches that are constituting this branch with the associated times."""

        at = Timestamp(at)

        if self.is_default:
            return {frozenset((GLOBAL_BRANCH_NAME, self.name)): at.to_string()}

        time_default_branch = Timestamp(self.branched_from)

        # If we are querying before the beginning of the branch
        # the time for the main branch must be the time of the query
        if self.ephemeral_rebase or not is_isolated or at < time_default_branch:
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

    async def delete(self, db: InfrahubDatabase) -> None:
        if self.is_default:
            raise ValidationError(f"Unable to delete {self.name} it is the default branch.")
        if self.is_global:
            raise ValidationError(f"Unable to delete {self.name} this is an internal branch.")
        await super().delete(db=db)
        query = await DeleteBranchRelationshipsQuery.init(db=db, branch_name=self.name)
        await query.execute(db=db)

    def get_query_filter_relationships(
        self, rel_labels: list, at: Optional[Union[Timestamp, str]] = None, include_outside_parentheses: bool = False
    ) -> Tuple[List, Dict]:
        """
        Generate a CYPHER Query filter based on a list of relationships to query a part of the graph at a specific time and on a specific branch.
        """

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

    def get_query_filter_path(
        self, at: Optional[Union[Timestamp, str]] = None, is_isolated: bool = True
    ) -> Tuple[str, Dict]:
        """
        Generate a CYPHER Query filter based on a path to query a part of the graph at a specific time and on a specific branch.

        Examples:
            >>> rels_filter, rels_params = self.branch.get_query_filter_path(at=self.at)
            >>> self.params.update(rels_params)
            >>> query += "\n WHERE all(r IN relationships(p) WHERE %s)" % rels_filter

            There is a currently an assumption that the relationship in the path will be named 'r'
        """

        at = Timestamp(at)
        branches_times = self.get_branches_and_times_to_query_global(at=at.to_string(), is_isolated=is_isolated)

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
        """
        Generate a CYPHER Query filter to query all events that are applicable to a given branch based
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
        """
        Generate a CYPHER Query filter to query a range of values in the graph between start_time and end_time."""

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

    async def rebase(self, db: InfrahubDatabase, at: Optional[Union[str, Timestamp]] = None):
        """Rebase the current Branch with its origin branch"""

        at = Timestamp(at)

        # Find all relationships with the name of the branch
        # Delete all relationship that have a to date defined in the past
        # Update the from time on all other relationships
        # If conflict is set, ignore the one with Drop

        await self.rebase_graph(db=db, at=at)

        # FIXME, we must ensure that there is no conflict before rebasing a branch
        #   Otherwise we could endup with a complicated situation
        self.branched_from = at.to_string()
        await self.save(db=db)

        # Update the branch in the registry after the rebase
        registry.branch[self.name] = self

    async def validate_branch(self, db: InfrahubDatabase) -> List[DataConflict]:
        """
        Validate if a branch is eligible to be merged.
        - Must be conflict free both for data and repository
        - All checks must pass
        - Check schema changes

        Need to support with and without rebase

        Need to return a list of violations, must be multiple
        """

        return await self.validate_graph(db=db)

    async def validate_graph(self, db: InfrahubDatabase) -> List[DataConflict]:
        # Check the diff and ensure the branch doesn't have some conflict
        diff = await self.diff(db=db)
        return await diff.get_conflicts(db=db)

    async def diff(
        self,
        db: InfrahubDatabase,
        branch_only: bool = False,
        diff_from: Optional[Union[str, Timestamp]] = None,
        diff_to: Optional[Union[str, Timestamp]] = None,
        namespaces_include: Optional[List[str]] = None,
        namespaces_exclude: Optional[List[str]] = None,
        kinds_include: Optional[List[str]] = None,
        kinds_exclude: Optional[List[str]] = None,
        branch_support: Optional[List[BranchSupportType]] = None,
    ) -> Diff:
        return await Diff.init(
            branch=self,
            diff_from=diff_from,
            diff_to=diff_to,
            branch_only=branch_only,
            namespaces_include=namespaces_include,
            namespaces_exclude=namespaces_exclude,
            kinds_include=kinds_include,
            kinds_exclude=kinds_exclude,
            branch_support=branch_support,
            db=db,
        )

    async def merge(
        self,
        db: InfrahubDatabase,
        rpc_client: Optional[InfrahubRpcClient] = None,
        at: Optional[Union[str, Timestamp]] = None,
        conflict_resolution: Optional[Dict[str, bool]] = None,
    ):
        """Merge the current branch into main."""
        conflict_resolution = conflict_resolution or {}
        conflicts = await self.validate_branch(db=db)

        if conflict_resolution:
            errors: List[str] = []
            for conflict in conflicts:
                if conflict.conflict_path not in conflict_resolution:
                    errors.append(str(conflict))

            if errors:
                raise ValidationError(
                    f"Unable to merge the branch '{self.name}', conflict resolution missing: {', '.join(errors)}"
                )

        elif conflicts:
            errors = [str(conflict) for conflict in conflicts]
            raise ValidationError(f"Unable to merge the branch '{self.name}', validation failed: {', '.join(errors)}")

        if self.name == config.SETTINGS.main.default_branch:
            raise ValidationError(f"Unable to merge the branch '{self.name}' into itself")

        # TODO need to find a way to properly communicate back to the user any issue that could come up during the merge
        # From the Graph or From the repositories
        await self.merge_graph(db=db, at=at, conflict_resolution=conflict_resolution)

        await self.merge_repositories(rpc_client=rpc_client, db=db)

    async def merge_graph(
        self,
        db: InfrahubDatabase,
        at: Optional[Union[str, Timestamp]] = None,
        conflict_resolution: Optional[Dict[str, bool]] = None,
    ):
        rel_ids_to_update = []
        conflict_resolution = conflict_resolution or {}

        default_branch: Branch = registry.branch[config.SETTINGS.main.default_branch]

        at = Timestamp(at)

        diff = await Diff.init(branch=self, db=db)
        nodes = await diff.get_nodes(db=db)

        if self.name in nodes:
            origin_nodes_query = await NodeListGetInfoQuery.init(
                db=db, ids=list(nodes[self.name].keys()), branch=default_branch
            )
            await origin_nodes_query.execute(db=db)
            origin_nodes = {
                node.get("n").get("uuid"): node for node in origin_nodes_query.get_results_group_by(("n", "uuid"))
            }

            # ---------------------------------------------
            # NODES
            # ---------------------------------------------
            for node_id, node in nodes[self.name].items():
                if node.action == DiffAction.ADDED:
                    query = await AddNodeToBranch.init(db=db, node_id=node.db_id, branch=default_branch)
                    await query.execute(db=db)
                    rel_ids_to_update.append(node.rel_id)

                elif node.action == DiffAction.REMOVED:
                    if node_id in origin_nodes:
                        query = await NodeDeleteQuery.init(db=db, branch=default_branch, node_id=node_id, at=at)
                        await query.execute(db=db)
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
                            db=db,
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
                            db=db,
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
                                db=db,
                            )
                            rel_ids_to_update.append(prop.rel_id)

                        elif prop.action == DiffAction.UPDATED and (
                            prop.path not in conflict_resolution or conflict_resolution[prop.path]
                        ):
                            await add_relationship(
                                src_node_id=attr.db_id,
                                dst_node_id=prop.db_id,
                                rel_type=prop_type,
                                at=at,
                                branch_name=default_branch.name,
                                branch_level=default_branch.hierarchy_level,
                                db=db,
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
                                db=db,
                            )
                            rel_ids_to_update.extend([prop.rel_id, prop.origin_rel_id])

        # ---------------------------------------------
        # RELATIONSHIPS
        # ---------------------------------------------
        rels = await diff.get_relationships(db=db)
        branch_relationships = rels.get(self.name, {})

        for rel_name in branch_relationships.keys():
            for _, rel in branch_relationships[rel_name].items():
                for node in rel.nodes.values():
                    matched_conflict_path = [path for path in rel.conflict_paths if path in conflict_resolution]
                    conflict_path = None
                    if matched_conflict_path:
                        conflict_path = matched_conflict_path[0]

                    if rel.action in [DiffAction.ADDED, DiffAction.REMOVED] and (
                        conflict_path not in conflict_resolution or conflict_resolution[conflict_path]
                    ):
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
                            db=db,
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
                        db=db,
                    )
                    rel_ids_to_update.append(prop.rel_id)

                    if rel.action in [DiffAction.UPDATED, DiffAction.REMOVED]:
                        rel_ids_to_update.append(prop.origin_rel_id)

        if rel_ids_to_update:
            await update_relationships_to(ids=rel_ids_to_update, to=at, db=db)

            # Update the branched_from time and update the registry
            # provided that an update is needed
            self.branched_from = Timestamp().to_string()
            await self.save(db=db)
            registry.branch[self.name] = self

    async def merge_repositories(self, db: InfrahubDatabase, rpc_client: Optional[InfrahubRpcClient] = None) -> None:
        # Collect all Repositories in Main because we'll need the commit in Main for each one.
        repos_in_main_list = await NodeManager.query(schema=InfrahubKind.REPOSITORY, db=db)
        repos_in_main = {repo.id: repo for repo in repos_in_main_list}

        repos_in_branch_list = await NodeManager.query(schema=InfrahubKind.REPOSITORY, db=db, branch=self)
        events = []
        for repo in repos_in_branch_list:
            # Check if the repo, exist in main, if not ignore this repo
            if repo.id not in repos_in_main:
                continue

            # repos_in_main[repo.id]
            # changed_files = repo.calculate_diff_with_commit(repo_in_main.commit.value)

            # if not changed_files:
            #     continue
            events.append(
                messages.GitRepositoryMerge(
                    repository_id=repo.id,
                    repository_name=repo.name.value,
                    source_branch=self.name,
                    destination_branch=config.SETTINGS.main.default_branch,
                )
            )

        if rpc_client:
            for event in events:
                await rpc_client.send(message=event)

    async def rebase_graph(self, db: InfrahubDatabase, at: Optional[Timestamp] = None):
        at = Timestamp(at)

        query = await GetAllBranchInternalRelationshipQuery.init(db=db, branch=self)
        await query.execute(db=db)

        rels_to_delete = []
        rels_to_update = []
        for result in query.get_results():
            element_id = result.get("r").element_id

            conflict_status = result.get("r").get("conflict", None)
            if conflict_status and conflict_status == "drop":
                rels_to_delete.append(element_id)
                continue

            time_to_str = result.get("r").get("to", None)
            time_from_str = result.get("r").get("from")
            time_from = Timestamp(time_from_str)

            if not time_to_str and time_from_str and time_from <= at:
                rels_to_update.append(element_id)
                continue

            if not time_to_str and time_from_str and time_from > at:
                rels_to_delete.append(element_id)
                continue

            time_to = Timestamp(time_to_str)
            if time_to < at:
                rels_to_delete.append(element_id)
                continue

            rels_to_update.append(element_id)

        update_query = await RebaseBranchUpdateRelationshipQuery.init(db=db, ids=rels_to_update, at=at)
        await update_query.execute(db=db)

        delete_query = await RebaseBranchDeleteRelationshipQuery.init(db=db, ids=rels_to_delete, at=at)
        await delete_query.execute(db=db)


class RelationshipPath(BaseModel):
    paths: List[str] = Field(default_factory=list)
    conflict_paths: List[str] = Field(default_factory=list)


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
    previous: Optional[Any] = None
    new: Optional[Any] = None

    def __hash__(self):
        return hash(type(self))


class PropertyDiffElement(BaseDiffElement):
    branch: str
    type: str
    action: DiffAction
    path: Optional[str] = None
    db_id: str = Field(exclude=True)
    rel_id: str = Field(exclude=True)
    origin_rel_id: Optional[str] = Field(None, exclude=True)
    value: Optional[ValueElement] = None
    changed_at: Optional[Timestamp] = None


class NodeAttributeDiffElement(BaseDiffElement):
    id: str
    name: str
    path: str
    action: DiffAction
    db_id: str = Field(exclude=True)
    rel_id: str = Field(exclude=True)
    origin_rel_id: Optional[str] = Field(None, exclude=True)
    changed_at: Optional[Timestamp] = None
    properties: Dict[str, PropertyDiffElement]


class NodeDiffElement(BaseDiffElement):
    branch: Optional[str] = None
    labels: List[str]
    kind: str
    id: str
    path: str
    action: DiffAction
    db_id: str = Field(exclude=True)
    rel_id: Optional[str] = Field(None, exclude=True)
    changed_at: Optional[Timestamp] = None
    attributes: Dict[str, NodeAttributeDiffElement]


class RelationshipEdgeNodeDiffElement(BaseDiffElement):
    id: str
    db_id: Optional[str] = Field(None, exclude=True)
    rel_id: Optional[str] = Field(None, exclude=True)
    labels: List[str]
    kind: str


class RelationshipDiffElement(BaseDiffElement):
    branch: Optional[str] = None
    id: str
    db_id: str = Field(exclude=True)
    name: str
    action: DiffAction
    nodes: Dict[str, RelationshipEdgeNodeDiffElement]
    properties: Dict[str, PropertyDiffElement]
    changed_at: Optional[Timestamp] = None
    paths: List[str]
    conflict_paths: List[str]

    def get_node_id_by_kind(self, kind: str) -> Optional[str]:
        ids = [rel.id for rel in self.nodes.values() if rel.kind == kind]
        if ids:
            return ids[0]
        return None


class FileDiffElement(BaseDiffElement):
    branch: str
    location: str
    repository: str
    action: DiffAction
    commit_from: str
    commit_to: str

    def __hash__(self):
        return hash((type(self),) + tuple(self.__dict__.values()))


class DiffSummaryElement(BaseModel):
    branch: str = Field(..., description="The branch where the change occured")
    node: str = Field(..., description="The unique ID of the node")
    kind: str = Field(..., description="The kind of the node as defined by its namespace and name")
    actions: List[DiffAction] = Field(..., description="A list of actions on this node.")

    def to_graphql(self) -> Dict[str, Union[str, List[str]]]:
        return {
            "branch": self.branch,
            "node": self.node,
            "kind": self.kind,
            "actions": [action.value for action in self.actions],
        }


class ModifiedPath(BaseModel):
    type: str
    node_id: str
    path_type: PathType
    kind: str
    element_name: Optional[str] = None
    property_name: Optional[str] = None
    peer_id: Optional[str] = None
    action: DiffAction
    change: Optional[ValueElement] = None

    def __eq__(self, other) -> bool:
        if not isinstance(other, ModifiedPath):
            raise NotImplementedError

        if self.modification_type != other.modification_type:
            return False

        if self.modification_type == "node":
            if self.action == other.action and self.action in [DiffAction.REMOVED, DiffAction.UPDATED]:
                return False

        if self.modification_type == "element":
            if self.action == other.action and self.action == DiffAction.REMOVED:
                return False

        return self.type == other.type and self.node_id == other.node_id

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ModifiedPath):
            raise NotImplementedError
        return str(self) < str(other)

    def __hash__(self):
        return hash((type(self),) + tuple(self.__dict__.values()))

    def _path(self, with_peer: bool = True) -> str:
        identifier = f"{self.type}/{self.node_id}"
        if self.element_name:
            identifier += f"/{self.element_name}"

        if self.path_type == PathType.RELATIONSHIP_ONE and not self.property_name:
            identifier += "/peer"

        if with_peer and self.peer_id:
            identifier += f"/{self.peer_id}"

        if self.property_name and self.property_name == "HAS_VALUE":
            identifier += "/value"
        elif self.property_name:
            identifier += f"/property/{self.property_name}"

        return identifier

    def __str__(self) -> str:
        return self._path()

    @property
    def change_type(self) -> str:
        if self.path_type in [PathType.ATTRIBUTE, PathType.RELATIONSHIP_MANY, PathType.RELATIONSHIP_ONE]:
            if self.property_name and self.property_name != "HAS_VALUE":
                return f"{self.path_type.value}_property"
            return f"{self.path_type.value}_value"
        return self.path_type.value

    @property
    def conflict_path(self) -> str:
        return self._path(with_peer=False)

    @property
    def modification_type(self) -> str:
        if self.element_name:
            return "element"

        return "node"


class BranchChanges(ValueElement):
    branch: str
    action: DiffAction


class ObjectConflict(BaseModel):
    name: str
    type: str
    kind: str
    id: str

    def to_conflict_dict(self) -> Dict[str, Any]:
        return self.dict()


class DataConflict(ObjectConflict):
    conflict_path: str
    path: str
    path_type: PathType
    property_name: Optional[str] = None
    change_type: str
    changes: List[BranchChanges] = Field(default_factory=list)

    def to_conflict_dict(self) -> Dict[str, Any]:
        conflict_dict = self.dict(exclude={"path_type"})
        conflict_dict["path_type"] = self.path_type.value
        return conflict_dict

    def __str__(self) -> str:
        return self.path


class SchemaConflict(ObjectConflict):
    path: str
    branch: str
    value: str


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
        namespaces_include: Optional[List[str]] = None,
        namespaces_exclude: Optional[List[str]] = None,
        kinds_include: Optional[List[str]] = None,
        kinds_exclude: Optional[List[str]] = None,
        branch_support: Optional[List[BranchSupportType]] = None,
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

        self.namespaces_include = namespaces_include
        self.namespaces_exclude = namespaces_exclude
        self.kinds_include = kinds_include
        self.kinds_exclude = kinds_exclude
        self.branch_support = branch_support or [BranchSupportType.AWARE]

        if not diff_from and self.branch.is_default:
            raise DiffFromRequiredOnDefaultBranchError(
                f"diff_from is mandatory when diffing on the default branch `{self.branch.name}`."
            )

        # If diff from hasn't been provided, we'll use the creation of the branch as the starting point
        if diff_from:
            self.diff_from = Timestamp(diff_from)
        else:
            self.diff_from = Timestamp(self.branch.created_at)

        # If diff_to hasn't been provided, we will use the current time.
        self.diff_to = Timestamp(diff_to)

        if self.diff_to < self.diff_from:
            raise DiffRangeValidationError("diff_to must be later than diff_from")

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
        db: InfrahubDatabase,
        branch: Branch,
        branch_only: bool = False,
        diff_from: Union[str, Timestamp] = None,
        diff_to: Union[str, Timestamp] = None,
        namespaces_include: Optional[List[str]] = None,
        namespaces_exclude: Optional[List[str]] = None,
        kinds_include: Optional[List[str]] = None,
        kinds_exclude: Optional[List[str]] = None,
        branch_support: Optional[List[BranchSupportType]] = None,
    ):
        origin_branch = await branch.get_origin_branch(db=db)

        return cls(
            branch=branch,
            origin_branch=origin_branch,
            branch_only=branch_only,
            diff_from=diff_from,
            diff_to=diff_to,
            namespaces_include=namespaces_include,
            namespaces_exclude=namespaces_exclude,
            kinds_include=kinds_include,
            kinds_exclude=kinds_exclude,
            branch_support=branch_support,
        )

    async def has_conflict(
        self,
        db: InfrahubDatabase,
        rpc_client: InfrahubRpcClient,  # pylint: disable=unused-argument
    ) -> bool:
        """Return True if the same path has been modified on multiple branches. False otherwise"""

        return await self.has_conflict_graph(db=db)

    async def has_conflict_graph(self, db: InfrahubDatabase) -> bool:
        """Return True if the same path has been modified on multiple branches. False otherwise"""

        if await self.get_conflicts_graph(db=db):
            return True

        return False

    async def has_changes(self, db: InfrahubDatabase, rpc_client: InfrahubRpcClient) -> bool:
        """Return True if the diff has identified some changes, False otherwise."""

        has_changes_graph = await self.has_changes_graph(db=db)
        has_changes_repositories = await self.has_changes_repositories(db=db, rpc_client=rpc_client)

        return has_changes_graph | has_changes_repositories

    async def has_changes_graph(self, db: InfrahubDatabase) -> bool:
        """Return True if the diff has identified some changes in the Graph, False otherwise."""

        mpaths = await self.get_modified_paths_graph(db=db)
        for _, paths in mpaths.items():
            if paths:
                return True

        return False

    async def has_changes_repositories(self, db: InfrahubDatabase, rpc_client: InfrahubRpcClient) -> bool:
        """Return True if the diff has identified some changes in the repositories, False otherwise."""

        mpaths = await self.get_modified_paths_repositories(db=db, rpc_client=rpc_client)
        for _, paths in mpaths.items():
            if paths:
                return True

        return False

    async def get_summary(self, db: InfrahubDatabase) -> List[DiffSummaryElement]:
        """Return a list of changed nodes and associated actions

        If only a relationship is modified for a given node it will have the updated action.
        """
        nodes = await self.get_nodes(db=db)
        relationships = await self.get_relationships(db=db)
        changes: Dict[str, Dict[str, DiffSummaryElement]] = {}

        for branch, branch_nodes in nodes.items():
            if branch not in changes:
                changes[branch] = {}
            for node_id, node in branch_nodes.items():
                if node_id not in changes[branch]:
                    changes[branch][node_id] = DiffSummaryElement(
                        branch=branch, node=node_id, kind=node.kind, actions=[node.action]
                    )
                if node.action not in changes[branch][node_id].actions:
                    changes[branch][node_id].actions.append(node.action)

        for branch, branch_relationships in relationships.items():
            if branch not in changes:
                changes[branch] = {}
            for relationship_type in branch_relationships.values():
                for relationship in relationship_type.values():
                    for node in relationship.nodes.values():
                        if node.id not in changes[branch]:
                            changes[branch][node.id] = DiffSummaryElement(
                                branch=branch, node=node.id, kind=node.kind, actions=[DiffAction.UPDATED]
                            )

        summary = []
        for branch in changes.values():
            for entry in branch.values():
                summary.append(entry)

        return summary

    async def get_conflicts(self, db: InfrahubDatabase) -> List[DataConflict]:
        """Return the list of conflicts identified by the diff as Path (tuple).

        For now we are not able to identify clearly enough the conflicts for the git repositories so this part is ignored.
        """
        return await self.get_conflicts_graph(db=db)

    async def get_conflicts_graph(self, db: InfrahubDatabase) -> List[DataConflict]:
        if self.branch_only:
            return []

        paths = await self.get_modified_paths_graph(db=db)

        # For now we assume that we can only have 2 branches but in the future we might need to support more
        branches = list(paths.keys())

        # if we don't have at least 2 branches returned we can safely assumed there is no conflict
        if len(branches) < 2:
            return []

        # Since we have 2 sets or tuple, we can quickly calculate the intersection using set(A) & set(B)
        conflicts = paths[branches[0]] & paths[branches[1]]

        branch0 = {str(conflict): conflict for conflict in paths[branches[0]]}
        branch1 = {str(conflict): conflict for conflict in paths[branches[1]]}
        changes = {branches[0]: branch0, branches[1]: branch1}
        responses = []
        for conflict in conflicts:
            response = DataConflict(
                name=conflict.element_name or "",
                type=conflict.type,
                id=conflict.node_id,
                kind=conflict.kind,
                path=str(conflict),
                change_type=conflict.change_type,
                conflict_path=conflict.conflict_path,
                path_type=conflict.path_type,
                property_name=conflict.property_name,
            )
            for branch, change in changes.items():
                if response.path in change and change[response.path]:
                    response.changes.append(
                        BranchChanges(
                            branch=branch,
                            action=change[response.path].action,
                            new=change[response.path].change.new,
                            previous=change[response.path].change.previous,
                        )
                    )
            responses.append(response)
        return responses

    async def get_modified_paths_graph(self, db: InfrahubDatabase) -> Dict[str, Set[ModifiedPath]]:
        """Return a list of all the modified paths in the graph per branch.

        Path for a node : ("node", node_id, attr_name, prop_type)
        Path for a relationship : ("relationships", rel_name, rel_id, prop_type

        Returns:
            Dict[str, set]: Returns a dictionnary by branch with a set of paths
        """

        paths = {}

        nodes = await self.get_nodes(db=db)
        for branch_name, data in nodes.items():
            if self.branch_only and branch_name != self.branch.name:
                continue

            if branch_name not in paths:
                paths[branch_name] = set()

            for node_id, node in data.items():
                modified_path = ModifiedPath(
                    type="data", kind=node.kind, node_id=node_id, action=node.action, path_type=PathType.NODE
                )
                paths[branch_name].add(modified_path)
                for attr_name, attr in node.attributes.items():
                    for prop_type, prop_value in attr.properties.items():
                        modified_path = ModifiedPath(
                            type="data",
                            kind=node.kind,
                            node_id=node_id,
                            action=attr.action,
                            element_name=attr_name,
                            path_type=PathType.ATTRIBUTE,
                            property_name=prop_type,
                            change=prop_value.value,
                        )
                        paths[branch_name].add(modified_path)

        relationships = await self.get_relationships(db=db)
        cardinality_one_branch_relationships: Dict[str, List[ModifiedPath]] = {}
        branch_kind_node: Dict[str, Dict[str, List[str]]] = {}
        display_label_map: Dict[str, Dict[str, str]] = {}
        kind_map: Dict[str, Dict[str, str]] = {}
        for branch_name in relationships.keys():
            branch_kind_node[branch_name] = {}
            cardinality_one_branch_relationships[branch_name] = []
            display_label_map[branch_name] = {}
            kind_map[branch_name] = {}

        for branch_name, data in relationships.items():  # pylint: disable=too-many-nested-blocks
            cardinality_one_relationships: Dict[str, ModifiedPath] = {}
            if self.branch_only and branch_name != self.branch.name:
                continue

            if branch_name not in paths:
                paths[branch_name] = set()

            for rel_name, rels in data.items():
                for _, rel in rels.items():
                    for node_id in rel.nodes:
                        neighbor_id = [neighbor for neighbor in rel.nodes.keys() if neighbor != node_id][0]
                        schema = registry.schema.get(name=rel.nodes[node_id].kind, branch=branch_name)
                        matching_relationship = [r for r in schema.relationships if r.identifier == rel_name]
                        if (
                            matching_relationship
                            and matching_relationship[0].cardinality == RelationshipCardinality.ONE
                        ):
                            relationship_key = f"{node_id}/{matching_relationship[0].name}"
                            if relationship_key not in cardinality_one_relationships:
                                cardinality_one_relationships[relationship_key] = ModifiedPath(
                                    type="data",
                                    node_id=node_id,
                                    action=DiffAction.UNCHANGED,
                                    kind=schema.kind,
                                    element_name=matching_relationship[0].name,
                                    path_type=PathType.from_relationship(matching_relationship[0].cardinality),
                                    change=ValueElement(),
                                )
                            peer_kind = matching_relationship[0].peer
                            if peer_kind not in branch_kind_node[branch_name]:
                                branch_kind_node[branch_name][peer_kind] = []
                            if rel.action == DiffAction.ADDED:
                                neighbor_id = rel.get_node_id_by_kind(kind=peer_kind)
                                cardinality_one_relationships[relationship_key].change.new = neighbor_id
                                branch_kind_node[branch_name][peer_kind].append(neighbor_id)
                            elif rel.action == DiffAction.REMOVED:
                                neighbor_id = rel.get_node_id_by_kind(kind=peer_kind)
                                cardinality_one_relationships[relationship_key].change.previous = neighbor_id
                                branch_kind_node[branch_name][peer_kind].append(neighbor_id)
                            if (
                                cardinality_one_relationships[relationship_key].change.previous
                                != cardinality_one_relationships[relationship_key].change.new
                            ):
                                cardinality_one_relationships[relationship_key].action = DiffAction.UPDATED
                        for prop_type, prop_value in rel.properties.items():
                            if matching_relationship:
                                modified_path = ModifiedPath(
                                    type="data",
                                    node_id=node_id,
                                    kind=schema.kind,
                                    action=rel.action,
                                    element_name=matching_relationship[0].name,
                                    path_type=PathType.from_relationship(matching_relationship[0].cardinality),
                                    property_name=prop_type,
                                    peer_id=neighbor_id,
                                    change=prop_value.value,
                                )
                                paths[branch_name].add(modified_path)

            for entry in cardinality_one_relationships.values():
                cardinality_one_branch_relationships[branch_name].append(entry)

        for branch_name, entries in branch_kind_node.items():
            for kind, ids in entries.items():
                schema = registry.schema.get(name=kind, branch=branch_name)
                fields = schema.generate_fields_for_display_label()
                nodes = await NodeManager.get_many(ids=ids, fields=fields, db=db, branch=branch_name)
                for node_id, node in nodes.items():
                    display_label_map[branch_name][node_id] = await node.render_display_label(db=db)
                    kind_map[branch_name][node_id] = kind

            for relationship in cardinality_one_branch_relationships[branch_name]:
                if relationship.change:
                    if mapped_name := display_label_map[branch_name].get(relationship.change.new):
                        relationship.change.new = {
                            "id": relationship.change.new,
                            "display_label": mapped_name,
                            "kind": kind_map[branch_name].get(relationship.change.new),
                        }
                    if mapped_name := display_label_map[branch_name].get(relationship.change.previous):
                        relationship.change.previous = {
                            "id": relationship.change.previous,
                            "display_label": mapped_name,
                            "kind": kind_map[branch_name].get(relationship.change.previous),
                        }
                if relationship.action != DiffAction.UNCHANGED:
                    paths[branch_name].add(relationship)

        return paths

    async def get_modified_paths_repositories(
        self, db: InfrahubDatabase, rpc_client: InfrahubRpcClient
    ) -> Dict[str, Set[Tuple]]:
        """Return a list of all the modified paths in the repositories.

        We need the commit values for each repository in the graph to calculate the difference.

        For now we are still assuming that a Branch always start from main
        """

        paths = defaultdict(set)

        for branch, items in await self.get_files_repositories_for_branch(
            db=db, rpc_client=rpc_client, branch=self.branch
        ):
            for item in items:
                paths[branch] = ("file", item.repository, item.location)

        if not self.branch_only:
            for branch, items in await self.get_modified_paths_repositories_for_branch(
                db=db, rpc_client=rpc_client, branch=self.origin_branch
            ):
                for item in items:
                    paths[branch] = ("file", item.repository, item.location)

        return paths

    async def get_modified_paths_repositories_for_branch(
        self, db: InfrahubDatabase, rpc_client: InfrahubRpcClient, branch: Branch
    ) -> Set[Tuple]:
        tasks = []
        paths = set()

        repos_to = {
            repo.id: repo
            for repo in await NodeManager.query(schema="Repository", db=db, branch=branch, at=self.diff_to)
        }
        repos_from = {
            repo.id: repo
            for repo in await NodeManager.query(schema="Repository", db=db, branch=branch, at=self.diff_from)
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
        self,
        rpc_client: InfrahubRpcClient,  # pylint: disable=unused-argument
        repository,
        commit_from: str,
        commit_to: str,
    ) -> Set[Tuple]:
        """Return the path of all the files that have changed for a given repository between 2 commits.

        Path format: ("file", repository.id, filename )
        """

        message = messages.GitDiffNamesOnly(
            repository_id=repository.id,
            repository_name=repository.name.value,  # type: ignore[attr-defined]
            repository_kind=repository.get_kind(),
            first_commit=commit_from,
            second_commit=commit_to,
        )

        reply = await services.service.message_bus.rpc(message=message)
        diff = reply.parse(response_class=DiffNamesResponse)

        return {("file", repository.id, filename) for filename in diff.files_changed}

    async def get_nodes(self, db: InfrahubDatabase) -> Dict[str, Dict[str, NodeDiffElement]]:
        """Return all the nodes calculated by the diff, organized by branch."""

        if not self._calculated_diff_nodes_at:
            await self._calculate_diff_nodes(db=db)

        return {
            branch_name: data["nodes"]
            for branch_name, data in self._results.items()
            if not self.branch_only or branch_name == self.branch.name
        }

    async def _calculate_diff_nodes(self, db: InfrahubDatabase):
        """Calculate the diff for all the nodes and attributes.

        The results will be stored in self._results organized by branch.
        """
        # ------------------------------------------------------------
        # Process nodes that have been Added or Removed first
        # ------------------------------------------------------------
        query_nodes = await DiffNodeQuery.init(
            db=db,
            branch=self.branch,
            diff_from=self.diff_from,
            diff_to=self.diff_to,
            namespaces_include=self.namespaces_include,
            namespaces_exclude=self.namespaces_exclude,
            kinds_include=self.kinds_include,
            kinds_exclude=self.kinds_exclude,
            branch_support=self.branch_support,
        )
        await query_nodes.execute(db=db)

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
                "path": f"data/{node_id}",
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
            db=db,
            branch=self.branch,
            diff_from=self.diff_from,
            diff_to=self.diff_to,
            namespaces_include=self.namespaces_include,
            namespaces_exclude=self.namespaces_exclude,
            kinds_include=self.kinds_include,
            kinds_exclude=self.kinds_exclude,
            branch_support=self.branch_support,
        )
        await query_attrs.execute(db=db)

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
                    "path": f"data/{node_id}",
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
                    "path": f"data/{node_id}/{attr_name}",
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
            db=db,
            ids=list(attrs_to_query),
            branch=self.branch,
            at=self.diff_from,
        )

        await origin_attr_query.execute(db=db)

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

            path = f"data/{node_id}/{attr_name}/property/{prop_type}"
            if prop_type == "HAS_VALUE":
                path = f"data/{node_id}/{attr_name}/value"

            item = {
                "type": prop_type,
                "branch": branch_name,
                "path": path,
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

    async def get_relationships(self, db: InfrahubDatabase) -> Dict[str, Dict[str, Dict[str, RelationshipDiffElement]]]:
        if not self._calculated_diff_rels_at:
            await self._calculated_diff_rels(db=db)

        return {
            branch_name: data["rels"]
            for branch_name, data in self._results.items()
            if not self.branch_only or branch_name == self.branch.name
        }

    async def get_relationships_per_node(
        self, db: InfrahubDatabase
    ) -> Dict[str, Dict[str, Dict[str, List[RelationshipDiffElement]]]]:
        rels = await self.get_relationships(db=db)

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

    async def get_node_id_per_kind(self, db: InfrahubDatabase) -> Dict[str, Dict[str, List[str]]]:
        # Node IDs organized per Branch and per Kind
        rels = await self.get_relationships(db=db)
        nodes = await self.get_nodes(db=db)

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

    async def _calculated_diff_rels(self, db: InfrahubDatabase):
        """Calculate the diff for all the relationships between Nodes.

        The results will be stored in self._results organized by branch.
        """

        rel_ids_to_query = []

        # ------------------------------------------------------------
        # Process first the main path of the relationships
        #   to identify the relationship that have been ADDED or DELETED
        # ------------------------------------------------------------
        query_rels = await DiffRelationshipQuery.init(
            db=db,
            branch=self.branch,
            diff_from=self.diff_from,
            diff_to=self.diff_to,
            namespaces_include=self.namespaces_include,
            namespaces_exclude=self.namespaces_exclude,
            kinds_include=self.kinds_include,
            kinds_exclude=self.kinds_exclude,
            branch_support=self.branch_support,
        )
        await query_rels.execute(db=db)

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

            relationship_paths = self.parse_relationship_paths(
                nodes=item["nodes"], branch_name=branch_name, relationship_name=rel_name
            )
            item["paths"] = relationship_paths.paths
            item["conflict_paths"] = relationship_paths.conflict_paths

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
            db=db, branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to
        )
        await query_props.execute(db=db)

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
            relationship_paths = self.parse_relationship_paths(
                nodes=item["nodes"], branch_name=branch_name, relationship_name=rel_name
            )
            item["paths"] = relationship_paths.paths
            item["conflict_paths"] = relationship_paths.conflict_paths

            self._results[branch_name]["rels"][rel_name][rel_id] = RelationshipDiffElement(**item)

            rel_ids_to_query.append(rel_id)

        # ------------------------------------------------------------
        # Query the current value of the relationships that have been flagged
        #  Usually we need more information to determine if the rel has been updated, added or removed
        # ------------------------------------------------------------
        origin_rel_properties_query = await DiffRelationshipPropertiesByIDSRangeQuery.init(
            db=db,
            ids=rel_ids_to_query,
            branch=self.branch,
            diff_from=self.diff_from,
            diff_to=self.diff_to,
        )
        await origin_rel_properties_query.execute(db=db)

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

    @staticmethod
    def parse_relationship_paths(
        nodes: Dict[str, RelationshipEdgeNodeDiffElement], branch_name: str, relationship_name: str
    ) -> RelationshipPath:
        node_ids = list(nodes.keys())
        neighbor_map = {node_ids[0]: node_ids[1], node_ids[1]: node_ids[0]}
        relationship_paths = RelationshipPath()
        for relationship in nodes.values():
            schema = registry.schema.get(name=relationship.kind, branch=branch_name)
            matching_relationship = [r for r in schema.relationships if r.identifier == relationship_name]
            relationship_path_name = "-undefined-"
            if matching_relationship:
                relationship_path_name = matching_relationship[0].name
            relationship_paths.paths.append(
                f"data/{relationship.id}/{relationship_path_name}/{neighbor_map[relationship.id]}"
            )
            relationship_paths.conflict_paths.append(f"data/{relationship.id}/{relationship_path_name}/peer")

        return relationship_paths

    async def get_files(self, db: InfrahubDatabase, rpc_client: InfrahubRpcClient) -> Dict[str, List[FileDiffElement]]:
        if not self._calculated_diff_files_at:
            await self._calculated_diff_files(db=db, rpc_client=rpc_client)

        return {
            branch_name: data["files"]
            for branch_name, data in self._results.items()
            if not self.branch_only or branch_name == self.branch.name
        }

    async def _calculated_diff_files(self, db: InfrahubDatabase, rpc_client: InfrahubRpcClient):
        self._results[self.branch.name]["files"] = await self.get_files_repositories_for_branch(
            db=db, rpc_client=rpc_client, branch=self.branch
        )

        if self.origin_branch:
            self._results[self.origin_branch.name]["files"] = await self.get_files_repositories_for_branch(
                db=db, rpc_client=rpc_client, branch=self.origin_branch
            )

        self._calculated_diff_files_at = Timestamp()

    async def get_files_repository(
        self,
        rpc_client: InfrahubRpcClient,  # pylint: disable=unused-argument
        branch_name: str,
        repository,
        commit_from: str,
        commit_to: str,
    ) -> List[FileDiffElement]:
        """Return all the files that have added, changed or removed for a given repository between 2 commits."""

        files = []

        message = messages.GitDiffNamesOnly(
            repository_id=repository.id,
            repository_name=repository.name.value,  # type: ignore[attr-defined]
            repository_kind=repository.get_kind(),
            first_commit=commit_from,
            second_commit=commit_to,
        )

        reply = await services.service.message_bus.rpc(message=message)
        diff = reply.parse(response_class=DiffNamesResponse)

        actions = {
            "files_changed": DiffAction.UPDATED,
            "files_added": DiffAction.ADDED,
            "files_removed": DiffAction.REMOVED,
        }

        for action_name, diff_action in actions.items():
            for filename in getattr(diff, action_name, []):
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
        self, db: InfrahubDatabase, rpc_client: InfrahubRpcClient, branch: Branch
    ) -> List[FileDiffElement]:
        tasks = []
        files = []

        repos_to = {
            repo.id: repo
            for repo in await NodeManager.query(
                schema=InfrahubKind.GENERICREPOSITORY, db=db, branch=branch, at=self.diff_to
            )
        }
        repos_from = {
            repo.id: repo
            for repo in await NodeManager.query(
                schema=InfrahubKind.GENERICREPOSITORY, db=db, branch=branch, at=self.diff_from
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
