from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import initialization
from infrahub.core.migrations.shared import InternalSchemaMigration, MigrationInput, MigrationResult, SchemaMigration
from infrahub.lock import initialize_lock
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class Migration074(InternalSchemaMigration):
    """Report schemas that violate the optional + human_friendly_id/uniqueness validation.

    Attributes referenced in human_friendly_id or uniqueness_constraints must be mandatory or have a
    default_value. Deployments that have optional attributes (with no default_value) referenced in these
    constraints would fail schema load after upgrade with strict mode enabled. This migration
    identifies such schemas so operators know exactly what to fix. This runs regardless of
    strict mode so users who disabled strict mode to bypass the validator still get a diagnostic.
    """

    name: str = "074_check_optional_hfid_uniqueness"
    description: str = (
        "Report schemas where an optional attribute with no default_value is referenced in "
        "human_friendly_id or uniqueness_constraints, which the new strict-mode validation rejects."
    )
    minimum_version: int = 73
    migrations: Sequence[SchemaMigration] = []

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        initialize_lock()
        await initialization(db=db)

        violation_messages: list[str] = []
        seen: set[tuple[str, str, str]] = set()

        branches = await Branch.get_list(db=db)
        for branch in branches:
            schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch, validate_schema=False)
            for kind in schema_branch.generic_names_without_templates + schema_branch.node_names:
                node_schema = schema_branch.get(name=kind, duplicate=False)

                constrained_attr_names: set[str] = set()
                if node_schema.human_friendly_id:
                    constrained_attr_names.update(
                        hfid_path.split("__")[0] for hfid_path in node_schema.human_friendly_id
                    )
                if node_schema.uniqueness_constraints:
                    for constraint in node_schema.uniqueness_constraints:
                        constrained_attr_names.update(constraint_path.split("__")[0] for constraint_path in constraint)

                if not constrained_attr_names:
                    continue

                for attr in node_schema.attributes:
                    if attr.name in constrained_attr_names and attr.optional and attr.default_value is None:
                        key = (branch.name, node_schema.kind, attr.name)
                        if key in seen:
                            continue
                        seen.add(key)
                        violation_messages.append(
                            f"Branch '{branch.name}': attribute '{attr.name}' of '{node_schema.kind}' is optional "
                            f"with no default_value but is referenced in human_friendly_id or uniqueness_constraints."
                        )

        if not violation_messages:
            return MigrationResult()

        header = (
            "The following schema violations were detected. Attributes referenced in human_friendly_id or "
            "uniqueness_constraints must be mandatory or have a default_value. Update these schemas before "
            "upgrading, or set INFRAHUB_SCHEMA_STRICT_MODE=false to bypass this validation while you migrate "
            "your schemas."
        )
        return MigrationResult(errors=[header] + violation_messages)

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
