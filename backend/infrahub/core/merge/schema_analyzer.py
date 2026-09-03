from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import BranchTrackingId, ConflictSelection
from infrahub.core.diff.query.filters import EnrichedDiffQueryFilters
from infrahub.core.models import SchemaUpdateValidationResult
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP

from .schema_builder import MergedSchemaBuilder  # noqa: TC001

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.models import SchemaDiff, SchemaUpdateConstraintInfo, SchemaUpdateMigrationInfo
    from infrahub.core.schema.manager import SchemaManager
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
        merged_schema_builder: MergedSchemaBuilder,
    ) -> None:
        self.db = db
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.diff_repository = diff_repository
        self.schema_manager = schema_manager
        self.merged_schema_builder = merged_schema_builder

        self._source_schema: SchemaBranch | None = None
        self._destination_schema: SchemaBranch | None = None
        self._common_ancestor_schema: SchemaBranch | None = None
        self._candidate_schema: SchemaBranch | None = None

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

        Symmetric, so a change made on the destination after the fork counts. Hashes only match
        when neither schema changed or both have converged on the same state.
        """
        return self.source_schema.get_hash() != self.destination_schema.get_hash()

    async def get_candidate_schema(self) -> SchemaBranch:
        """The schema the branches will share once the source is merged into the destination."""
        if self._candidate_schema:
            return self._candidate_schema

        if not self.schemas_differ():
            self._candidate_schema = self.destination_schema.duplicate()
            return self._candidate_schema

        self._candidate_schema = self.merged_schema_builder.build(
            ancestor=await self.get_common_ancestor_schema(),
            source=self.source_schema,
            destination=self.destination_schema,
            keep_destination_property_map=await self._get_properties_kept_from_destination(),
        )
        return self._candidate_schema

    async def _get_properties_kept_from_destination(self) -> dict[str, set[str]]:
        tracking_id = BranchTrackingId(name=self.source_branch.name)
        conflicted_node_uuids = await self.diff_repository.get_conflicted_node_uuids(
            diff_branch_name=self.source_branch.name, tracking_id=tracking_id
        )
        if not conflicted_node_uuids:
            return {}

        enriched_diff = await self.diff_repository.get_one(
            diff_branch_name=self.source_branch.name,
            tracking_id=tracking_id,
            filters=EnrichedDiffQueryFilters(ids=list(conflicted_node_uuids)),
        )
        return self.properties_kept_from_destination(enriched_diff)

    @staticmethod
    def three_way_schema_diff(*, source: SchemaBranch, destination: SchemaBranch, target: SchemaBranch) -> SchemaDiff:
        """Everything either branch changed since they forked, keyed by the names the target uses.

        Each side is compared with the schema the operation produces rather than with the ancestor:
        what separates the destination from the target is the source's contribution, and what
        separates the source from the target is the destination's. A diff is keyed by the names of
        the schema it is compared with, so measuring from the ancestor would key each half by that
        side's own names and a renamed element would be reported under two names, one of which the
        target does not know; validation and migration calculation both resolve every kind and field
        on the target.
        """
        return destination.diff(other=target) + source.diff(other=target)

    @staticmethod
    def schema_diff_constraints(
        *, source: SchemaBranch, destination: SchemaBranch, target_schema: SchemaBranch
    ) -> list[SchemaUpdateConstraintInfo]:
        """Constraints the schema comparison contributes, all unrestricted in scope.

        A property change gated on a migration produces a migration entry rather than a constraint, so
        those are turned back into constraints where a checker exists for them; otherwise the check
        would only ever arrive node-scoped from the data diff.
        """
        diff = MergeSchemaAnalyzer.three_way_schema_diff(source=source, destination=destination, target=target_schema)
        validation = SchemaUpdateValidationResult.init(diff=diff, schema=target_schema)
        validation.add_validator_for_migration(validator_map=CONSTRAINT_VALIDATOR_MAP)
        return validation.constraints

    @staticmethod
    def properties_kept_from_destination(enriched_diff: EnrichedDiffRoot) -> dict[str, set[str]]:
        """Value conflicts a user resolved in the destination's favour, by node uuid and field name.

        The graph merge skips these paths, so the merged schema keeps the destination's value for each
        of them. Only value conflicts are collected: a conflict over whether a node exists at all is
        not expressible as a property to leave alone.
        """
        kept: dict[str, set[str]] = {}
        for node in enriched_diff.nodes:
            for attribute in node.attributes:
                for prop in attribute.properties:
                    conflict = prop.conflict
                    if (
                        prop.property_type is DatabaseEdgeType.HAS_VALUE
                        and conflict
                        and conflict.resolvable
                        and conflict.selected_branch is ConflictSelection.BASE_BRANCH
                    ):
                        kept.setdefault(node.uuid, set()).add(attribute.name)
        return kept

    async def get_3ways_diff_schema(self) -> SchemaDiff:
        """Both sides' changes, keyed by the names the candidate schema uses.

        The candidate is the only target compared with here, never a schema loaded back from the
        database after the operation: the candidate is built from the two registry schemas, so every
        kind the registry knows is on both sides of each comparison. A schema loaded from the database
        holds only what the database holds, and a kind absent from it would read as removed.
        """
        return self.three_way_schema_diff(
            source=self.source_schema,
            destination=self.destination_schema,
            target=await self.get_candidate_schema(),
        )

    async def calculate_migrations(self) -> list[SchemaUpdateMigrationInfo]:
        """Migrations both sides' changes imply, resolved against the candidate schema."""
        validation = SchemaUpdateValidationResult.init(
            diff=await self.get_3ways_diff_schema(), schema=await self.get_candidate_schema()
        )
        return validation.migrations

    async def calculate_validations(self) -> list[SchemaUpdateConstraintInfo]:
        """Constraints both sides' changes imply, resolved against the candidate schema."""
        return self.schema_diff_constraints(
            source=self.source_schema,
            destination=self.destination_schema,
            target_schema=await self.get_candidate_schema(),
        )
