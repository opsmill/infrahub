from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.models import SchemaUpdateValidationResult
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.models import SchemaUpdateConstraintInfo, SchemaUpdateMigrationInfo
    from infrahub.core.schema.manager import SchemaDiff, SchemaManager
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class MergeSchemaAnalyzer:
    """Compare the source and destination branch schemas to derive merge/rebase migrations and validations."""

    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        diff_repository: DiffRepository,
        schema_manager: SchemaManager,
    ) -> None:
        self.db = db
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.diff_repository = diff_repository
        self.schema_manager = schema_manager

        self._source_schema: SchemaBranch | None = None
        self._destination_schema: SchemaBranch | None = None
        self._common_ancestor_schema: SchemaBranch | None = None

    @property
    def source_schema(self) -> SchemaBranch:
        if not self._source_schema:
            self._source_schema = self.schema_manager.get_schema_branch(name=self.source_branch.name).duplicate()

        return self._source_schema

    @property
    def destination_schema(self) -> SchemaBranch:
        if not self._destination_schema:
            self._destination_schema = self.schema_manager.get_schema_branch(
                name=self.destination_branch.name
            ).duplicate()

        return self._destination_schema

    @property
    def common_ancestor_schema(self) -> SchemaBranch:
        if self._common_ancestor_schema:
            return self._common_ancestor_schema
        raise ValueError("_common_ancestor_schema hasn't been initialized")

    async def get_common_ancestor_schema(self) -> SchemaBranch:
        """Retrieve the schema of the source branch when the branch was created.

        Using the destination schema at ``branched_from`` ensures that changes on the destination
        branch that have been added to the source branch via rebases are properly reflected.

        For now we are querying the full schema, but this is something we'll need to revisit in the future by either:
         - having a faster way to pull a previous version of the schema
         - using the diff generated from the data.
        """
        if self._common_ancestor_schema:
            return self._common_ancestor_schema

        self._common_ancestor_schema = await self.schema_manager.load_schema_from_db(
            db=self.db,
            branch=self.destination_branch,
            at=Timestamp(self.source_branch.branched_from),
        )

        return self._common_ancestor_schema

    def schemas_differ(self) -> bool:
        """Whether the two branches hold different schemas.

        Symmetric, so a change made on the destination after the fork counts. A branch keeps the
        schema it forked with until it is rebased, so its hash only matches the destination's when
        neither side has moved or both have converged on the same state.
        """
        return self.source_schema.get_hash() != self.destination_schema.get_hash()

    async def has_schema_changes(self) -> bool:
        diff_summary = await self.diff_repository.summary(
            base_branch_name=self.destination_branch.name,
            diff_branch_names=[self.source_branch.name],
            tracking_id=BranchTrackingId(name=self.source_branch.name),
            # SchemaGeneric omitted: a generic's migration-relevant changes surface on Attribute/Relationships and inheriting SchemaNodes
            filters={"kind": {"includes": ["SchemaNode", "SchemaAttribute", "SchemaRelationship"]}},
        )
        if not diff_summary:
            return False
        return bool(diff_summary.num_added or diff_summary.num_removed or diff_summary.num_updated)

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
        common_ancestor_schema = await self.get_common_ancestor_schema()

        diff_source = common_ancestor_schema.diff(other=self.source_schema)
        diff_destination = common_ancestor_schema.diff(other=self.destination_schema)
        return diff_source + diff_destination

    async def calculate_migrations(self, target_schema: SchemaBranch) -> list[SchemaUpdateMigrationInfo]:
        diff_3way = await self.get_3ways_diff_schema()
        validation = SchemaUpdateValidationResult.init(diff=diff_3way, schema=target_schema)
        return validation.migrations

    async def calculate_validations(self, target_schema: SchemaBranch) -> list[SchemaUpdateConstraintInfo]:
        diff_3way = await self.get_3ways_diff_schema()
        validation = SchemaUpdateValidationResult.init(diff=diff_3way, schema=target_schema)
        return validation.constraints
