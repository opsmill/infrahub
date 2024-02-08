from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union

from infrahub import config
from infrahub.core.constants import (
    DiffAction,
    InfrahubKind,
    RelationshipStatus,
)
from infrahub.core.manager import NodeManager
from infrahub.core.query.branch import (
    AddNodeToBranch,
)
from infrahub.core.query.node import NodeDeleteQuery, NodeListGetInfoQuery
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import add_relationship, update_relationships_to
from infrahub.exceptions import (
    ValidationError,
)
from infrahub.message_bus import messages

from .diff import BranchDiffer, DataConflict

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.message_bus.rpc import InfrahubRpcClient

    from .branch import Branch


class BranchMerger:
    def __init__(self, branch: Branch):
        self.branch = branch

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
        diff = await BranchDiffer.init(db=db, branch=self.branch)
        return await diff.get_conflicts(db=db)

    async def merge(
        self,
        db: InfrahubDatabase,
        rpc_client: Optional[InfrahubRpcClient] = None,
        at: Optional[Union[str, Timestamp]] = None,
        conflict_resolution: Optional[Dict[str, bool]] = None,
    ) -> None:
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
                    f"Unable to merge the branch '{self.branch.name}', conflict resolution missing: {', '.join(errors)}"
                )

        elif conflicts:
            errors = [str(conflict) for conflict in conflicts]
            raise ValidationError(
                f"Unable to merge the branch '{self.branch.name}', validation failed: {', '.join(errors)}"
            )

        if self.branch.name == config.SETTINGS.main.default_branch:
            raise ValidationError(f"Unable to merge the branch '{self.branch.name}' into itself")

        # TODO need to find a way to properly communicate back to the user any issue that could come up during the merge
        # From the Graph or From the repositories
        await self.merge_graph(db=db, at=at, conflict_resolution=conflict_resolution)

        await self.merge_repositories(rpc_client=rpc_client, db=db)

    async def merge_graph(  # pylint: disable=too-many-branches,too-many-statements
        self,
        db: InfrahubDatabase,
        at: Optional[Union[str, Timestamp]] = None,
        conflict_resolution: Optional[Dict[str, bool]] = None,
    ) -> None:
        rel_ids_to_update: List[str] = []
        conflict_resolution = conflict_resolution or {}

        default_branch: Branch = registry.branch[config.SETTINGS.main.default_branch]

        at = Timestamp(at)

        diff = await BranchDiffer.init(branch=self.branch, db=db)
        nodes = await diff.get_nodes(db=db)

        if self.branch.name in nodes:
            origin_nodes_query = await NodeListGetInfoQuery.init(
                db=db, ids=list(nodes[self.branch.name].keys()), branch=default_branch
            )
            await origin_nodes_query.execute(db=db)
            origin_nodes = {
                node.get("n").get("uuid"): node for node in origin_nodes_query.get_results_group_by(("n", "uuid"))
            }

            # ---------------------------------------------
            # NODES
            # ---------------------------------------------
            for node_id, node in nodes[self.branch.name].items():
                if node.action == DiffAction.ADDED:
                    query1 = await AddNodeToBranch.init(db=db, node_id=node.db_id, branch=default_branch)
                    await query1.execute(db=db)
                    if node.rel_id:
                        rel_ids_to_update.append(node.rel_id)

                elif node.action == DiffAction.REMOVED:
                    if node_id in origin_nodes:
                        query2 = await NodeDeleteQuery.init(db=db, branch=default_branch, node_id=node_id, at=at)
                        await query2.execute(db=db)
                        if node.rel_id:
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

                    elif attr.action == DiffAction.REMOVED and attr.origin_rel_id:
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

                        elif (
                            prop.action == DiffAction.UPDATED
                            and (prop.path not in conflict_resolution or conflict_resolution[prop.path])
                            and prop.origin_rel_id
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

                        elif prop.action == DiffAction.REMOVED and prop.origin_rel_id:
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
        branch_relationships = rels.get(self.branch.name, {})

        for rel_name in branch_relationships.keys():
            for _, rel_element in branch_relationships[rel_name].items():
                for rel_node in rel_element.nodes.values():
                    matched_conflict_path = [path for path in rel_element.conflict_paths if path in conflict_resolution]
                    conflict_path = None
                    if matched_conflict_path:
                        conflict_path = matched_conflict_path[0]

                    if rel_element.action in [DiffAction.ADDED, DiffAction.REMOVED] and (
                        conflict_path not in conflict_resolution or conflict_resolution[conflict_path]
                    ):
                        rel_status = RelationshipStatus.ACTIVE
                        if rel_element.action == DiffAction.REMOVED:
                            rel_status = RelationshipStatus.DELETED

                        if not rel_node.rel_id or not rel_node.db_id or not rel_element.db_id:
                            raise ValueError("node.rel_id, rel_node.db_id and rel_element.db_id must be defined")

                        await add_relationship(
                            src_node_id=rel_node.db_id,
                            dst_node_id=rel_element.db_id,
                            rel_type="IS_RELATED",
                            at=at,
                            branch_name=default_branch.name,
                            branch_level=default_branch.hierarchy_level,
                            status=rel_status,
                            db=db,
                        )
                        rel_ids_to_update.append(rel_node.rel_id)

                for prop_type, prop in rel_element.properties.items():
                    rel_status = RelationshipStatus.ACTIVE
                    if prop.action == DiffAction.REMOVED:
                        rel_status = RelationshipStatus.DELETED

                    await add_relationship(
                        src_node_id=rel_element.db_id,
                        dst_node_id=prop.db_id,
                        rel_type=prop.type,
                        at=at,
                        branch_name=default_branch.name,
                        branch_level=default_branch.hierarchy_level,
                        db=db,
                    )
                    rel_ids_to_update.append(prop.rel_id)

                    if rel_element.action in [DiffAction.UPDATED, DiffAction.REMOVED] and prop.origin_rel_id:
                        rel_ids_to_update.append(prop.origin_rel_id)

        if rel_ids_to_update:
            await update_relationships_to(ids=rel_ids_to_update, to=at, db=db)

            # Update the branched_from time and update the registry
            # provided that an update is needed
            self.branch.branched_from = Timestamp().to_string()
            await self.branch.save(db=db)
            registry.branch[self.branch.name] = self

    async def merge_repositories(self, db: InfrahubDatabase, rpc_client: Optional[InfrahubRpcClient] = None) -> None:
        # Collect all Repositories in Main because we'll need the commit in Main for each one.
        repos_in_main_list = await NodeManager.query(schema=InfrahubKind.REPOSITORY, db=db)
        repos_in_main = {repo.id: repo for repo in repos_in_main_list}

        repos_in_branch_list = await NodeManager.query(schema=InfrahubKind.REPOSITORY, db=db, branch=self.branch)
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
                    repository_name=repo.name.value,  # type: ignore[attr-defined]
                    source_branch=self.branch.name,
                    destination_branch=config.SETTINGS.main.default_branch,
                )
            )

        if rpc_client:
            for event in events:
                await rpc_client.send(message=event)
