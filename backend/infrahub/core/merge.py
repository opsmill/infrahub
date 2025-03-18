from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import RepositoryInternalStatus
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.manager import NodeManager
from infrahub.core.models import SchemaUpdateValidationResult
from infrahub.core.protocols import CoreRepository
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError
from infrahub.log import get_logger

from ..git.models import GitRepositoryMerge
from ..workflows.catalogue import GIT_REPOSITORIES_MERGE

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.coordinator import DiffCoordinator
    from infrahub.core.diff.merger.merger import DiffMerger
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.models import SchemaUpdateConstraintInfo, SchemaUpdateMigrationInfo
    from infrahub.core.schema.manager import SchemaDiff
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


log = get_logger()


class BranchMerger:
    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        diff_coordinator: DiffCoordinator,
        diff_merger: DiffMerger,
        diff_repository: DiffRepository,
        destination_branch: Branch | None = None,
        service: InfrahubServices | None = None,
    ):
        self.source_branch = source_branch
        self.destination_branch: Branch = destination_branch or registry.get_branch_from_registry()
        self.db = db
        self.diff_coordinator = diff_coordinator
        self.diff_merger = diff_merger
        self.diff_repository = diff_repository
        self.migrations: list[SchemaUpdateMigrationInfo] = []
        self._merge_at = Timestamp()

        self._source_schema: SchemaBranch | None = None
        self._destination_schema: SchemaBranch | None = None
        self._initial_source_schema: SchemaBranch | None = None

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
        diff_summary = await self.diff_repository.summary(
            base_branch_name=self.destination_branch.name,
            diff_branch_names=[self.source_branch.name],
            tracking_id=BranchTrackingId(name=self.source_branch.name),
            filters={"kind": {"includes": ["SchemaNode", "SchemaAttribute", "SchemaRelationship"]}},
        )
        if not diff_summary:
            return False
        return bool(diff_summary.num_added or diff_summary.num_removed or diff_summary.num_updated)

    async def update_schema(self) -> bool:
        """After the merge, if there was some changes, we need to:
        - update the schema in the registry
        - Identify if we need to execute some migrations
        """

        # NOTE we need to revisit how to calculate an accurate diff to pull only what needs to be updated from the schema
        # for now the best solution is to pull everything to ensure the integrity of the schema

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

    async def merge(
        self,
        at: str | Timestamp | None = None,
    ) -> EnrichedDiffRoot:
        """Merge the current branch into main."""
        if self.source_branch.name == registry.default_branch:
            raise ValidationError(f"Unable to merge the branch '{self.source_branch.name}' into itself")

        log.info("Updating diff for merge")
        await self.diff_coordinator.update_branch_diff(
            base_branch=self.destination_branch, diff_branch=self.source_branch
        )
        log.info("Diff updated for merge")

        errors: list[str] = []
        async for conflict_path, conflict in self.diff_repository.get_all_conflicts_for_diff(
            diff_branch_name=self.source_branch.name, tracking_id=BranchTrackingId(name=self.source_branch.name)
        ):
            if conflict.selected_branch is None or conflict.resolvable is False:
                errors.append(conflict_path)

        if errors:
            raise ValidationError(
                f"Unable to merge the branch '{self.source_branch.name}', conflict resolution missing: {', '.join(errors)}"
            )

        # TODO need to find a way to properly communicate back to the user any issue that could come up during the merge
        # From the Graph or From the repositories
        self._merge_at = Timestamp(at)
        branch_diff = await self.diff_merger.merge_graph(at=self._merge_at)
        await self.merge_repositories()
        return branch_diff

    async def rollback(self) -> None:
        await self.diff_merger.rollback(at=self._merge_at)

    async def merge_repositories(self) -> None:
        # Collect all Repositories in Main because we'll need the commit in Main for each one.
        repos_in_main_list = await NodeManager.query(schema=CoreRepository, db=self.db)
        repos_in_main = {repo.id: repo for repo in repos_in_main_list}

        repos_in_branch_list = await NodeManager.query(schema=CoreRepository, db=self.db, branch=self.source_branch)
        for repo in repos_in_branch_list:
            # Check if the repo, exist in main, if not ignore this repo
            if repo.id not in repos_in_main:
                continue

            if repo.internal_status.value == RepositoryInternalStatus.INACTIVE.value:
                continue

            if self.source_branch.sync_with_git or repo.internal_status.value == RepositoryInternalStatus.STAGING.value:
                model = GitRepositoryMerge(
                    repository_id=repo.id,
                    repository_name=repo.name.value,
                    internal_status=repo.internal_status.value,
                    source_branch=self.source_branch.name,
                    destination_branch=self.destination_branch.name,
                    destination_branch_id=str(self.destination_branch.get_uuid()),
                    default_branch=repo.default_branch.value,
                )
                await self.service.workflow.submit_workflow(
                    workflow=GIT_REPOSITORIES_MERGE, parameters={"model": model}
                )
