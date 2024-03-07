from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union

from infrahub import config
from infrahub.core.constants import (
    DiffAction,
    InfrahubKind,
    RelationshipStatus,
)
from infrahub.core.manager import NodeManager
from infrahub.core.models import SchemaBranchDiff
from infrahub.core.query.branch import (
    AddNodeToBranch,
)
from infrahub.core.query.node import NodeDeleteQuery, NodeListGetInfoQuery
from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema, NodeSchema
from infrahub.core.schema_manager import SchemaUpdateValidationResult
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import add_relationship, update_relationships_to
from infrahub.exceptions import (
    ValidationError,
)
from infrahub.message_bus import messages

from .diff.branch_differ import BranchDiffer

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.core.schema_manager import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

    from .diff.model import DataConflict


class BranchMerger:
    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Optional[Branch] = None,
        service: Optional[InfrahubServices] = None,
    ):
        self.source_branch = source_branch
        self.destination_branch = destination_branch or registry.get_branch_from_registry()
        self.db = db
        self.migrations: List[SchemaUpdateMigrationInfo] = []
        self._graph_diff: Optional[BranchDiffer] = None

        self._source_schema: Optional[SchemaBranch] = None
        self._destination_schema: Optional[SchemaBranch] = None

        self._service = service

    @property
    def source_schema(self) -> SchemaBranch:
        if not self._source_schema:
            self._source_schema = registry.schema.get_schema_branch(name=self.source_branch.name).duplicate()

        return self._source_schema

    @property
    def destination_schema(self) -> SchemaBranch:
        if not self._destination_schema:
            self._destination_schema = registry.schema.get_schema_branch(name=self.destination_branch.name).duplicate()

        return self._destination_schema

    @property
    def service(self) -> InfrahubServices:
        if not self._service:
            raise ValueError("BranchMerger hasn't been initialized with a service object")
        return self._service

    async def get_graph_diff(self) -> BranchDiffer:
        if not self._graph_diff:
            self._graph_diff = await BranchDiffer.init(db=self.db, branch=self.source_branch)

        return self._graph_diff

    async def get_schema_diff(self) -> SchemaBranchDiff:
        """Return a SchemaBranchDiff object with the list of nodes and generics
        based on the information returned by the Graph Diff.

        The Graph Diff return a list of UUID so we need to convert that back into Kind
        """

        graph_diff = await self.get_graph_diff()
        schema_summary = await graph_diff.get_schema_summary()

        schema_diff = SchemaBranchDiff()

        # NOTE At this point there is no Generic in the schema but this could change in the future
        for element in schema_summary.get(self.source_branch.name, []):
            node = self.source_schema.get_by_id(id=element.node)
            if isinstance(node, NodeSchema):
                schema_diff.nodes.append(node.kind)
            elif isinstance(node, GenericSchema):
                schema_diff.generics.append(node.kind)

        for element in schema_summary.get(self.destination_branch.name, []):
            node = self.destination_schema.get_by_id(id=element.node)
            if isinstance(node, NodeSchema):
                schema_diff.nodes.append(node.kind)
            elif isinstance(node, GenericSchema):
                schema_diff.generics.append(node.kind)

        # Remove duplicates if any
        schema_diff.nodes = list(set(schema_diff.nodes))
        schema_diff.generics = list(set(schema_diff.generics))

        return schema_diff

    async def update_schema(self) -> bool:
        """After the merge, if there was some changes, we need to:
        - update the schema in the registry
        - Identify if we need to execute some migrations
        """

        schema_diff = await self.get_schema_diff()

        if not schema_diff.has_diff:
            return False

        updated_schema = await registry.schema.load_schema_from_db(
            db=self.db,
            branch=self.destination_branch,
            schema=self.destination_schema.duplicate(),
            schema_diff=schema_diff,
        )
        registry.schema.set_schema_branch(name=self.destination_branch.name, schema=updated_schema)
        self.destination_branch.update_schema_hash()
        await self.destination_branch.save(db=self.db)

        # To calculate the migrations that we need to execute we need
        # the initial version of the schema when the branch was created
        # and we need to calculate a 3 ways comparison between
        # - The initial schema and the current schema in the source branch
        # - The initial schema and the current schema in the destination branch
        initial_source_schema = await registry.schema.load_schema_from_db(
            db=self.db,
            branch=self.source_branch,
            schema=self.source_schema.duplicate(),
            schema_diff=schema_diff,
            at=Timestamp(self.source_branch.branched_from),
        )

        diff_source = initial_source_schema.diff(other=self.source_schema)
        diff_destination = initial_source_schema.diff(other=self.destination_schema)
        diff_both = diff_source + diff_destination

        validation = SchemaUpdateValidationResult.init(diff=diff_both, schema=updated_schema)
        self.migrations = validation.migrations

        return True

    async def validate_branch(self) -> List[DataConflict]:
        """
        Validate if a branch is eligible to be merged.
        - Must be conflict free both for data and repository
        - All checks must pass
        - Check schema changes

        Need to support with and without rebase

        Need to return a list of violations, must be multiple
        """

        return await self.validate_graph()

    async def validate_graph(self) -> List[DataConflict]:
        # Check the diff and ensure the branch doesn't have some conflict
        diff = await self.get_graph_diff()
        return await diff.get_conflicts()

    async def merge(
        self,
        at: Optional[Union[str, Timestamp]] = None,
        conflict_resolution: Optional[Dict[str, bool]] = None,
    ) -> None:
        """Merge the current branch into main."""
        conflict_resolution = conflict_resolution or {}
        conflicts = await self.validate_branch()

        if conflict_resolution:
            errors: List[str] = []
            for conflict in conflicts:
                if conflict.conflict_path not in conflict_resolution:
                    errors.append(str(conflict))

            if errors:
                raise ValidationError(
                    f"Unable to merge the branch '{self.source_branch.name}', conflict resolution missing: {', '.join(errors)}"
                )

        elif conflicts:
            errors = [str(conflict) for conflict in conflicts]
            raise ValidationError(
                f"Unable to merge the branch '{self.source_branch.name}', validation failed: {', '.join(errors)}"
            )

        if self.source_branch.name == config.SETTINGS.main.default_branch:
            raise ValidationError(f"Unable to merge the branch '{self.source_branch.name}' into itself")

        # TODO need to find a way to properly communicate back to the user any issue that could come up during the merge
        # From the Graph or From the repositories
        await self.merge_graph(at=at, conflict_resolution=conflict_resolution)
        await self.merge_repositories()

    async def merge_graph(  # pylint: disable=too-many-branches,too-many-statements
        self,
        at: Optional[Union[str, Timestamp]] = None,
        conflict_resolution: Optional[Dict[str, bool]] = None,
    ) -> None:
        rel_ids_to_update: List[str] = []
        conflict_resolution = conflict_resolution or {}

        default_branch: Branch = registry.branch[config.SETTINGS.main.default_branch]

        at = Timestamp(at)

        diff = await self.get_graph_diff()
        nodes = await diff.get_nodes()

        if self.source_branch.name in nodes:
            origin_nodes_query = await NodeListGetInfoQuery.init(
                db=self.db, ids=list(nodes[self.source_branch.name].keys()), branch=default_branch
            )
            await origin_nodes_query.execute(db=self.db)
            origin_nodes = {
                node.get("n").get("uuid"): node for node in origin_nodes_query.get_results_group_by(("n", "uuid"))
            }

            # ---------------------------------------------
            # NODES
            # ---------------------------------------------
            for node_id, node in nodes[self.source_branch.name].items():
                if node.action == DiffAction.ADDED:
                    query1 = await AddNodeToBranch.init(db=self.db, node_id=node.db_id, branch=default_branch)
                    await query1.execute(db=self.db)
                    if node.rel_id:
                        rel_ids_to_update.append(node.rel_id)

                elif node.action == DiffAction.REMOVED:
                    if node_id in origin_nodes:
                        query2 = await NodeDeleteQuery.init(db=self.db, branch=default_branch, node_id=node_id, at=at)
                        await query2.execute(db=self.db)
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
                            db=self.db,
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
                            db=self.db,
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
                                db=self.db,
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
                                db=self.db,
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
                                db=self.db,
                            )
                            rel_ids_to_update.extend([prop.rel_id, prop.origin_rel_id])

        # ---------------------------------------------
        # RELATIONSHIPS
        # ---------------------------------------------
        rels = await diff.get_relationships()
        branch_relationships = rels.get(self.source_branch.name, {})

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
                            db=self.db,
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
                        db=self.db,
                    )
                    rel_ids_to_update.append(prop.rel_id)

                    if rel_element.action in [DiffAction.UPDATED, DiffAction.REMOVED] and prop.origin_rel_id:
                        rel_ids_to_update.append(prop.origin_rel_id)

        if rel_ids_to_update:
            await update_relationships_to(ids=rel_ids_to_update, to=at, db=self.db)

            # Update the branched_from time and update the registry
            # provided that an update is needed
            self.source_branch.branched_from = Timestamp().to_string()
            await self.source_branch.save(db=self.db)
            registry.branch[self.source_branch.name] = self.source_branch

    async def merge_repositories(self) -> None:
        # Collect all Repositories in Main because we'll need the commit in Main for each one.
        repos_in_main_list = await NodeManager.query(schema=InfrahubKind.REPOSITORY, db=self.db)
        repos_in_main = {repo.id: repo for repo in repos_in_main_list}

        repos_in_branch_list = await NodeManager.query(
            schema=InfrahubKind.REPOSITORY, db=self.db, branch=self.source_branch
        )
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
                    source_branch=self.source_branch.name,
                    destination_branch=config.SETTINGS.main.default_branch,
                )
            )

        for event in events:
            await self.service.send(message=event)
