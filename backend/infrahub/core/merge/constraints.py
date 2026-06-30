from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.diff.model.diff import SchemaConflict
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.models import SchemaUpdateConstraintInfo
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.validators.model import SchemaViolation
    from infrahub.core.validators.models.validate_migration import SchemaValidatorPathResponseData
    from infrahub.database import InfrahubDatabase


@dataclass
class MergeConstraintValidationResult:
    violations: list[SchemaViolation] = field(default_factory=list)
    schema_conflicts: list[SchemaConflict] = field(default_factory=list)


@dataclass(frozen=True)
class ConflictedField:
    """A node field (identified by node id and field name) that has a diff conflict on the branch."""

    node_id: str
    field_name: str


async def gather_conflicted_fields(diff_repository: DiffRepository, branch_name: str) -> set[ConflictedField]:
    """Return the fields that have a diff conflict on the branch.

    A field with a diff conflict is reconciled by the conflict resolution applied during the merge, so
    a constraint violation reported on it would reflect the pre-resolution cross-branch state and must
    be skipped (see ``build_merge_constraint_result``).
    """
    conflicted_fields: set[ConflictedField] = set()
    async for conflict_path, _conflict in diff_repository.get_all_conflicts_for_diff(
        diff_branch_name=branch_name, tracking_id=BranchTrackingId(name=branch_name)
    ):
        # path_identifier is "data/<node_uuid>/<field>/...".
        path_parts = conflict_path.split("/")
        if len(path_parts) >= 3 and path_parts[0] == "data":
            conflicted_fields.add(ConflictedField(node_id=path_parts[1], field_name=path_parts[2]))
    return conflicted_fields


def build_merge_constraint_result(
    responses: list[SchemaValidatorPathResponseData],
    conflicted_fields: set[ConflictedField],
    branch: str,
) -> MergeConstraintValidationResult:
    """Collect constraint violations, skipping any whose field is reconciled by a diff conflict.

    A violation on a field that has a diff conflict reflects the pre-resolution cross-branch state; the
    conflict resolution applied during the merge reconciles that field, so flagging it here would be a
    spurious (and non-resolvable) violation and it is skipped.
    """
    result = MergeConstraintValidationResult()
    for response in responses:
        field_name = response.schema_path.field_name
        for violation in response.violations:
            if (
                field_name is not None
                and ConflictedField(node_id=violation.node_id, field_name=field_name) in conflicted_fields
            ):
                continue
            result.violations.append(violation)
            result.schema_conflicts.append(
                SchemaConflict(
                    name=response.schema_path.get_path(),
                    type=response.constraint_name,
                    kind=violation.node_kind,
                    id=violation.node_id,
                    path=response.schema_path.get_path(),
                    value=violation.message,
                    branch=branch,
                )
            )
    return result


class MergeConstraintValidator:
    """Validate that merging a branch will not violate any schema/data constraint on the destination.

    The constraints are derived from both the data diff (e.g. a new value that breaks a uniqueness
    constraint) and the schema diff (e.g. a relationship becoming mandatory). A violation on a field
    that has a diff conflict is ignored: that field is reconciled by the conflict resolution applied
    during the merge, so its pre-resolution cross-branch state is not a real violation.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch, diff_repository: DiffRepository) -> None:
        self.db = db
        self.branch = branch
        self.diff_repository = diff_repository

    async def validate(
        self, candidate_schema: SchemaBranch, schema_diff_constraints: list[SchemaUpdateConstraintInfo]
    ) -> MergeConstraintValidationResult:
        determiner = ConstraintValidatorDeterminer(schema_branch=candidate_schema)
        node_field_summaries = await self.diff_repository.get_node_field_summaries(
            diff_branch_name=self.branch.name, tracking_id=BranchTrackingId(name=self.branch.name)
        )
        data_diff_constraints = await determiner.get_constraints(node_diffs=node_field_summaries)
        constraints = set(data_diff_constraints + schema_diff_constraints)
        if not constraints:
            return MergeConstraintValidationResult()

        responses = await schema_validate_migrations(
            message=SchemaValidateMigrationData(
                branch=self.branch, schema_branch=candidate_schema, constraints=list(constraints)
            )
        )
        conflicted_fields = await gather_conflicted_fields(
            diff_repository=self.diff_repository, branch_name=self.branch.name
        )
        return build_merge_constraint_result(
            responses=responses, conflicted_fields=conflicted_fields, branch=self.branch.name
        )
