from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.migrations.schema.tasks import schema_apply_migrations
from infrahub.core.query.rollback import RollbackQuery
from infrahub.exceptions import MigrationError
from infrahub.log import get_logger
from infrahub.workflows.catalogue import SCHEMA_APPLY_MIGRATION

if TYPE_CHECKING:
    import logging

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.models import SchemaDiff, SchemaUpdateMigrationInfo
    from infrahub.core.schema.manager import SchemaManager
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.workflow import InfrahubWorkflow


_default_log = get_logger()


class MigrationExecutor(Enum):
    """Determines how migrations are executed."""

    DIRECT = "direct"  # Call schema_apply_migrations directly (for tasks)
    WORKFLOW = "workflow"  # Execute via workflow service (for API)


@dataclass
class SchemaUpdateResult:
    """Result of a schema update operation."""

    updated_hash: str | None = None
    error_messages: list[str] | None = None
    exception: Exception | None = None

    @property
    def success(self) -> bool:
        return not self.error_messages and self.exception is None


class SchemaUpdateCoordinator:
    """Coordinates schema updates and migrations with unified timestamps and rollback on failure.

    This class encapsulates the logic for:
    1. Updating schema in the database with a unified timestamp
    2. Running migrations (either directly or via workflow service)
    3. Rolling back all changes on failure
    4. Restoring registry state and branch hash
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        schema_manager: SchemaManager,
        origin_schema: SchemaBranch,
        workflow: InfrahubWorkflow | None = None,
        context: InfrahubContext | None = None,
        migration_executor: MigrationExecutor = MigrationExecutor.WORKFLOW,
        logger: logging.Logger | logging.LoggerAdapter[logging.Logger] | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            db: Database connection
            branch: Branch being updated
            schema_manager: Schema manager for updating schema in DB and registry
            origin_schema: Original schema before update (for rollback)
            workflow: Workflow service for executing migrations (required for WORKFLOW executor)
            context: Infrahub context (required for WORKFLOW executor)
            migration_executor: How to execute migrations (DIRECT or WORKFLOW)
            logger: Logger to use (defaults to module logger)
        """
        self.db = db
        self.branch = branch
        self.schema_manager = schema_manager
        self.origin_schema = origin_schema
        self.workflow = workflow
        self.context = context
        self.migration_executor = migration_executor
        self.log = logger or _default_log

        if self.migration_executor is MigrationExecutor.WORKFLOW and (self.workflow is None or self.context is None):
            raise RuntimeError("Workflow and context are required for WORKFLOW executor")

    def _get_workflow(self) -> InfrahubWorkflow:
        """Get workflow service, raising if not available."""
        if self.workflow is None:
            raise RuntimeError("Workflow service is required but not provided")
        return self.workflow

    def _get_context(self) -> InfrahubContext:
        """Get context, raising if not available."""
        if self.context is None:
            raise RuntimeError("Context is required but not provided")
        return self.context

    async def execute(
        self,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        diff: SchemaDiff | None = None,
        migrations: list[SchemaUpdateMigrationInfo] | None = None,
        limit: list[str] | None = None,
        update_db: bool = True,
        update_registry: bool = True,
        user_id: str = SYSTEM_USER_ID,
    ) -> SchemaUpdateResult:
        """Execute the schema update with migrations and rollback on failure.

        Args:
            candidate_schema: New schema to apply
            at: Timestamp for all operations (enables atomic rollback)
            diff: Schema diff for update_schema_branch (optional, for incremental updates)
            migrations: List of migrations to run
            limit: Limit schema update to specific items
            update_db: Whether to update the database (implies update_registry=True)
            update_registry: Whether to update the registry (used when DB already updated externally)
            user_id: User ID for all operations

        Returns:
            SchemaUpdateResult with success status and details

        Raises:
            MigrationError: If migrations fail and rollback completes
            Exception: Original exception if migrations fail via exception
        """

        # Step 1: Update schema in DB and/or registry
        updated_hash: str | None = None
        if update_db or update_registry:
            updated_hash = await self._update_schema(
                candidate_schema=candidate_schema,
                at=at,
                diff=diff,
                limit=limit,
                update_db=update_db,
                update_registry=update_registry,
                user_id=user_id,
            )

        if not migrations:
            return SchemaUpdateResult(updated_hash=updated_hash)

        # Step 2: Run migrations
        error_msgs, exception = await self._run_migrations(
            candidate_schema=candidate_schema,
            at=at,
            migrations=migrations,
            user_id=user_id,
        )

        # Step 3: Check for failures
        if not error_msgs and exception is None:
            return SchemaUpdateResult(updated_hash=updated_hash)

        if exception:
            self.log.error(  # type: ignore[call-arg]
                "Schema migration failed, beginning rollback",
                branch=self.branch.name,
                error=str(exception),
            )
        else:
            self.log.error(  # type: ignore[call-arg]
                "Schema migration returned errors, beginning rollback",
                branch=self.branch.name,
                errors=error_msgs,
            )

        # Step 4: Rollback on failure
        await self._rollback(at=at)
        await self._restore_registry_state()

        self.log.info("Schema rollback completed", branch=self.branch.name)  # type: ignore[call-arg]

        # Re-raise the appropriate error
        if exception:
            raise exception
        raise MigrationError(message=",\n".join(error_msgs))

    async def _update_schema(
        self,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        diff: SchemaDiff | None,
        limit: list[str] | None,
        update_db: bool,
        update_registry: bool,
        user_id: str,
    ) -> str:
        """Update schema in database and/or registry.

        Args:
            candidate_schema: The new schema to apply
            at: Timestamp for DB operations
            diff: Schema diff for incremental updates
            limit: Limit to specific schema items
            update_db: If True, update DB via update_schema_branch.
            update_registry: If True, update registry via set_schema_branch.
        Returns:
            The updated schema hash
        """
        if update_db:
            await self.schema_manager.update_schema_branch(
                schema=candidate_schema,
                db=self.db,
                branch=self.branch.name,
                diff=diff,
                limit=limit,
                update_db=True,
                at=at,
                user_id=user_id,
            )
        if update_registry:
            self.schema_manager.set_schema_branch(name=self.branch.name, schema=candidate_schema)

        self.branch.update_schema_hash()
        self.log.info(  # type: ignore[call-arg]
            "Schema has been updated", branch=self.branch.name, hash=self.branch.active_schema_hash.main
        )
        await self.branch.save(db=self.db, user_id=user_id)

        return candidate_schema.get_hash()

    async def _run_migrations(
        self,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        migrations: list[SchemaUpdateMigrationInfo],
        user_id: str,
    ) -> tuple[list[str], Exception | None]:
        """Run migrations using the configured executor."""
        apply_migration_data = SchemaApplyMigrationData(
            branch=self.branch,
            new_schema=candidate_schema,
            previous_schema=self.origin_schema,
            migrations=migrations,
            at=at,
            user_id=user_id,
        )

        if self.migration_executor == MigrationExecutor.WORKFLOW:
            return await self._run_migrations_via_workflow(apply_migration_data=apply_migration_data)
        return await self._run_migrations_directly(apply_migration_data=apply_migration_data)

    async def _run_migrations_via_workflow(
        self,
        apply_migration_data: SchemaApplyMigrationData,
    ) -> tuple[list[str], Exception | None]:
        """Execute migrations via workflow service."""
        workflow = self._get_workflow()
        context = self._get_context()

        error_msgs: list[str] = []
        exception: Exception | None = None

        try:
            error_msgs = await workflow.execute_workflow(
                workflow=SCHEMA_APPLY_MIGRATION,
                context=context,
                expected_return=list[str],
                parameters={"message": apply_migration_data},
            )
        except Exception as exc:
            exception = exc

        return error_msgs, exception

    async def _run_migrations_directly(
        self,
        apply_migration_data: SchemaApplyMigrationData,
    ) -> tuple[list[str], Exception | None]:
        """Execute migrations directly (for branch tasks)."""

        error_msgs: list[str] = []
        exception: Exception | None = None

        try:
            error_msgs = await schema_apply_migrations(message=apply_migration_data)
        except Exception as exc:
            exception = exc

        return error_msgs, exception

    async def _rollback(self, at: Timestamp) -> None:
        """Rollback all changes made at the unified timestamp."""
        rollback_query = await RollbackQuery.init(
            db=self.db,
            branch=self.branch,
            target_branch=self.branch,
            at=at,
        )
        await rollback_query.execute(db=self.db)

    async def _restore_registry_state(self) -> None:
        """Restore original schema in registry and reset branch hash."""
        self.schema_manager.set_schema_branch(name=self.branch.name, schema=self.origin_schema)
        self.branch.update_schema_hash()
        await self.branch.save(db=self.db)
