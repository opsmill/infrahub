from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from infrahub.core.constants import DiffAction, RepositoryInternalStatus
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.manager import NodeManager
from infrahub.core.models import SchemaBranchDiff, SchemaUpdateValidationResult
from infrahub.core.protocols import CoreRepository
from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema, NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import ValidationError
from infrahub.message_bus import messages

from .diff.branch_differ import BranchDiffer

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.models import SchemaUpdateConstraintInfo, SchemaUpdateMigrationInfo
    from infrahub.core.schema.manager import SchemaDiff
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

    from .diff.model.diff import DataConflict


class BranchMerger:
    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Optional[Branch] = None,
        service: Optional[InfrahubServices] = None,
    ):
        self.source_branch = source_branch
        self.destination_branch: Branch = destination_branch or registry.get_branch_from_registry()
        self.db = db
        self.migrations: list[SchemaUpdateMigrationInfo] = []
        self._graph_diff: Optional[BranchDiffer] = None

        self._source_schema: Optional[SchemaBranch] = None
        self._destination_schema: Optional[SchemaBranch] = None
        self._initial_source_schema: Optional[SchemaBranch] = None

        self.schema_diff: Optional[SchemaBranchDiff] = None

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
    def initial_source_schema(self) -> SchemaBranch:
        if self._initial_source_schema:
            return self._initial_source_schema
        raise ValueError("_initial_source_schema hasn't been initialized")

    @property
    def service(self) -> InfrahubServices:
        if not self._service:
            raise ValueError("BranchMerger hasn't been initialized with a service object")
        return self._service

    async def get_graph_diff(self) -> BranchDiffer:
        if not self._graph_diff:
            self._graph_diff = await BranchDiffer.init(db=self.db, branch=self.source_branch)

        return self._graph_diff

    async def get_initial_source_branch(self) -> SchemaBranch:
        """Retrieve the schema of the source branch when the branch was created.
        For now we are querying the full schema, but this is something we'll need to revisit in the future by either:
         - having a faster way to pull a previous version of the schema
         - using the diff generated from the data
        """
        if self._initial_source_schema:
            return self._initial_source_schema

        self._initial_source_schema = await registry.schema.load_schema_from_db(
            db=self.db,
            branch=self.source_branch,
            at=Timestamp(self.source_branch.created_at),
        )

        return self._initial_source_schema

    async def has_schema_changes(self) -> bool:
        graph_diff = await self.get_graph_diff()
        return await graph_diff.has_schema_changes()

    async def get_schema_diff(self) -> SchemaBranchDiff:
        """Return a SchemaBranchDiff object with the list of nodes and generics
        based on the information returned by the Graph Diff.

        The Graph Diff return a list of UUID so we need to convert that back into Kind
        """

        if self.schema_diff:
            return self.schema_diff

        graph_diff = await self.get_graph_diff()
        schema_summary = await graph_diff.get_schema_summary()
        schema_diff = SchemaBranchDiff()

        # NOTE At this point there is no Generic in the schema but this could change in the future
        for element in schema_summary.get(self.source_branch.name, []):
            if element.kind == "SchemaNode" and DiffAction.REMOVED in element.actions:
                continue
            node = self.source_schema.get_by_any_id(id=element.node)
            if isinstance(node, NodeSchema):
                schema_diff.nodes.append(node.kind)
            elif isinstance(node, GenericSchema):
                schema_diff.generics.append(node.kind)

        for element in schema_summary.get(self.destination_branch.name, []):
            if element.kind == "SchemaNode" and DiffAction.REMOVED in element.actions:
                continue
            node = self.destination_schema.get_by_any_id(id=element.node)
            if isinstance(node, NodeSchema):
                schema_diff.nodes.append(node.kind)
            elif isinstance(node, GenericSchema):
                schema_diff.generics.append(node.kind)

        # Remove duplicates if any
        schema_diff.nodes = list(set(schema_diff.nodes))
        schema_diff.generics = list(set(schema_diff.generics))

        self.schema_diff = schema_diff
        return self.schema_diff

    async def update_schema(self) -> bool:
        """After the merge, if there was some changes, we need to:
        - update the schema in the registry
        - Identify if we need to execute some migrations
        """

        # NOTE we need to revisit how to calculate an accurate diff to pull only what needs to be updated from the schema
        # for now the best solution is to pull everything to ensure the integrity of the schema
        # schema_diff = await self.get_schema_diff()

        if not await self.has_schema_changes():
            return False

        updated_schema = await registry.schema.load_schema_from_db(
            db=self.db,
            branch=self.destination_branch,
            # schema=self.destination_schema.duplicate(),
            # schema_diff=schema_diff,
        )
        registry.schema.set_schema_branch(name=self.destination_branch.name, schema=updated_schema)
        self.destination_branch.update_schema_hash()
        await self.destination_branch.save(db=self.db)

        await self.calculate_migrations(target_schema=updated_schema)

        return True

    def get_candidate_schema(self) -> SchemaBranch:
        # For now, we retrieve the latest schema for each branch from the registry
        # In the future it would be good to generate the object SchemaUpdateValidationResult from message.branch_diff
        current_schema = self.source_schema.duplicate()
        candidate_schema = self.destination_schema.duplicate()
        candidate_schema.update(schema=current_schema)

        return candidate_schema

    async def get_3ways_diff_schema(self) -> SchemaDiff:
        # To calculate the migrations that we need to execute we need
        # the initial version of the schema when the branch was created
        # and we need to calculate a 3 ways comparison between
        # - The initial schema and the current schema in the source branch
        # - The initial schema and the current schema in the destination branch
        initial_source_schema = await self.get_initial_source_branch()

        diff_source = initial_source_schema.diff(other=self.source_schema)
        diff_destination = initial_source_schema.diff(other=self.destination_schema)
        diff_both = diff_source + diff_destination

        return diff_both

    async def calculate_migrations(self, target_schema: SchemaBranch) -> list[SchemaUpdateMigrationInfo]:
        diff_3way = await self.get_3ways_diff_schema()
        validation = SchemaUpdateValidationResult.init(diff=diff_3way, schema=target_schema)
        self.migrations = validation.migrations
        return self.migrations

    async def calculate_validations(self, target_schema: SchemaBranch) -> list[SchemaUpdateConstraintInfo]:
        diff_3way = await self.get_3ways_diff_schema()
        validation = SchemaUpdateValidationResult.init(diff=diff_3way, schema=target_schema)
        return validation.constraints

    async def validate_branch(self) -> list[DataConflict]:
        """
        Validate if a branch is eligible to be merged.
        - Must be conflict free both for data and repository
        - All checks must pass
        - Check schema changes

        Need to support with and without rebase

        Need to return a list of violations, must be multiple
        """

        return await self.validate_graph()

    async def validate_graph(self) -> list[DataConflict]:
        # Check the diff and ensure the branch doesn't have some conflict
        diff = await self.get_graph_diff()
        return await diff.get_conflicts()

    async def merge(
        self,
        at: Optional[Union[str, Timestamp]] = None,
        conflict_resolution: Optional[dict[str, bool]] = None,
    ) -> None:
        """Merge the current branch into main."""
        conflict_resolution = conflict_resolution or {}
        conflicts = await self.validate_branch()

        if conflict_resolution:
            errors: list[str] = []
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

        if self.source_branch.name == registry.default_branch:
            raise ValidationError(f"Unable to merge the branch '{self.source_branch.name}' into itself")

        # TODO need to find a way to properly communicate back to the user any issue that could come up during the merge
        # From the Graph or From the repositories
        at = Timestamp(at)
        await self.merge_graph(at=at)
        await self.merge_repositories()

    async def merge_graph(
        self,
        at: Timestamp,
    ) -> None:
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(
            DiffCoordinator, db=self.db, branch=self.source_branch
        )
        await diff_coordinator.update_branch_diff(base_branch=self.destination_branch, diff_branch=self.source_branch)
        diff_merger = await component_registry.get_component(DiffMerger, db=self.db, branch=self.source_branch)
        await diff_merger.merge_graph(at=at)

    async def merge_repositories(self) -> None:
        # Collect all Repositories in Main because we'll need the commit in Main for each one.
        repos_in_main_list = await NodeManager.query(schema=CoreRepository, db=self.db)
        repos_in_main = {repo.id: repo for repo in repos_in_main_list}

        repos_in_branch_list = await NodeManager.query(schema=CoreRepository, db=self.db, branch=self.source_branch)
        events = []
        for repo in repos_in_branch_list:
            # Check if the repo, exist in main, if not ignore this repo
            if repo.id not in repos_in_main:
                continue

            if repo.internal_status.value == RepositoryInternalStatus.INACTIVE.value:
                continue

            if self.source_branch.sync_with_git or repo.internal_status.value == RepositoryInternalStatus.STAGING.value:
                events.append(
                    messages.GitRepositoryMerge(
                        repository_id=repo.id,
                        repository_name=repo.name.value,
                        internal_status=repo.internal_status.value,
                        source_branch=self.source_branch.name,
                        destination_branch=registry.default_branch,
                        default_branch=repo.default_branch.value,
                    )
                )

        for event in events:
            await self.service.send(message=event)
