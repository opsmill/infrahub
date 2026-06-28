from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Literal, NoReturn, overload

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

    DIRECT = "direct"  # Call schema_apply_migrations directly
    WORKFLOW = "workflow"  # Execute via workflow service


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
        schema_manager: SchemaManager,
        workflow: InfrahubWorkflow | None = None,
        logger: logging.Logger | logging.LoggerAdapter[logging.Logger] | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            db: Database connection
            schema_manager: Schema manager for updating schema in DB and registry
            workflow: Workflow service for executing migrations (required for the WORKFLOW executor)
            logger: Logger to use (defaults to module logger)

        """
        self.db = db
        self.schema_manager = schema_manager
        self.workflow = workflow
        self.log = logger or _default_log

    def _get_workflow(self) -> InfrahubWorkflow:
        """Get workflow service, raising if not available.

        Raises:
            RuntimeError: When the workflow service has not been provided to the coordinator.

        """
        if self.workflow is None:
            raise RuntimeError("Workflow service is required but not provided")
        return self.workflow

    @overload
    async def execute(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        context: InfrahubContext | None = ...,
        migration_executor: MigrationExecutor = ...,
        diff: SchemaDiff | None = ...,
        migrations: list[SchemaUpdateMigrationInfo] | None = ...,
        limit: list[str] | None = ...,
        update_db: Literal[True] = True,
        update_registry: bool = ...,
        user_id: str = ...,
        manage_rollback: bool = ...,
    ) -> str: ...

    @overload
    async def execute(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        context: InfrahubContext | None = ...,
        migration_executor: MigrationExecutor = ...,
        diff: SchemaDiff | None = ...,
        migrations: list[SchemaUpdateMigrationInfo] | None = ...,
        limit: list[str] | None = ...,
        update_db: Literal[False] = ...,
        update_registry: Literal[True] = ...,
        user_id: str = ...,
        manage_rollback: bool = ...,
    ) -> str: ...

    @overload
    async def execute(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        context: InfrahubContext | None = ...,
        migration_executor: MigrationExecutor = ...,
        diff: SchemaDiff | None = ...,
        migrations: list[SchemaUpdateMigrationInfo] | None = ...,
        limit: list[str] | None = ...,
        update_db: Literal[False] = ...,
        update_registry: Literal[False] = ...,
        user_id: str = ...,
        manage_rollback: bool = ...,
    ) -> str | None: ...

    async def execute(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        context: InfrahubContext | None = None,
        migration_executor: MigrationExecutor = MigrationExecutor.WORKFLOW,
        diff: SchemaDiff | None = None,
        migrations: list[SchemaUpdateMigrationInfo] | None = None,
        limit: list[str] | None = None,
        update_db: bool = True,
        update_registry: bool = True,
        user_id: str = SYSTEM_USER_ID,
        manage_rollback: bool = True,
    ) -> str | None:
        """Execute the schema update with migrations and rollback on failure.

        Args:
            branch: Branch being updated
            origin_schema: Original schema before the update (for rollback)
            candidate_schema: New schema to apply
            at: Timestamp for all operations (enables atomic rollback)
            context: Infrahub context (required for the WORKFLOW executor)
            migration_executor: How to execute migrations (DIRECT or WORKFLOW)
            diff: Schema diff for update_schema_branch (optional, for incremental updates)
            migrations: List of migrations to run
            limit: Limit schema update to specific items
            update_db: Whether to update the database
            update_registry: Whether to update the registry (used when DB already updated externally)
            user_id: User ID for all operations
            manage_rollback: When True (default), this coordinator handles its own rollback on
                failure (DB rollback + registry restore). When False, exceptions propagate without
                triggering internal rollback.

        Returns:
            The updated schema hash, or None if the schema was not updated

        Raises:
            RuntimeError: When migrations must run via the WORKFLOW executor but workflow or context is not provided.
            MigrationError: If migrations fail and rollback completes
            Exception: Original exception if migrations fail via exception

        """
        if (
            migrations
            and migration_executor is MigrationExecutor.WORKFLOW
            and (self.workflow is None or context is None)
        ):
            raise RuntimeError("Workflow and context are required for WORKFLOW executor")

        # Step 1: Update schema in DB and/or registry
        updated_hash: str | None = None
        if update_db or update_registry:
            try:
                updated_hash = await self._update_schema(
                    branch=branch,
                    candidate_schema=candidate_schema,
                    at=at,
                    diff=diff,
                    limit=limit,
                    update_db=update_db,
                    update_registry=update_registry,
                    user_id=user_id,
                )
            except Exception as exc:
                if manage_rollback:
                    await self._handle_failure_and_rollback(
                        branch=branch, origin_schema=origin_schema, at=at, phase="update", exception=exc, error_msgs=[]
                    )
                raise

        if not migrations:
            return updated_hash

        # Step 2: Run migrations
        error_msgs, exception = await self._run_migrations(
            branch=branch,
            origin_schema=origin_schema,
            candidate_schema=candidate_schema,
            at=at,
            migrations=migrations,
            migration_executor=migration_executor,
            context=context,
            user_id=user_id,
        )

        if error_msgs or exception is not None:
            if manage_rollback:
                await self._handle_failure_and_rollback(
                    branch=branch,
                    origin_schema=origin_schema,
                    at=at,
                    phase="migration",
                    exception=exception,
                    error_msgs=error_msgs,
                )
            if exception:
                raise exception
            raise MigrationError(message=",\n".join(error_msgs))

        return updated_hash

    async def _update_schema(
        self,
        branch: Branch,
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
            branch: The branch being updated
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
                branch=branch.name,
                diff=diff,
                limit=limit,
                update_db=True,
                at=at,
                user_id=user_id,
            )
        if update_registry:
            self.schema_manager.set_schema_branch(name=branch.name, schema=candidate_schema)

        branch.update_schema_hash()
        self.log.info("Schema has been updated", extra={"branch": branch.name, "hash": branch.active_schema_hash.main})
        await branch.save(db=self.db, user_id=user_id)

        return candidate_schema.get_hash()

    async def _run_migrations(
        self,
        branch: Branch,
        origin_schema: SchemaBranch,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        migrations: list[SchemaUpdateMigrationInfo],
        migration_executor: MigrationExecutor,
        context: InfrahubContext | None,
        user_id: str,
    ) -> tuple[list[str], Exception | None]:
        """Run migrations using the configured executor."""
        apply_migration_data = SchemaApplyMigrationData(
            branch=branch,
            new_schema=candidate_schema,
            previous_schema=origin_schema,
            migrations=migrations,
            at=at,
            user_id=user_id,
        )

        if migration_executor == MigrationExecutor.WORKFLOW:
            return await self._run_migrations_via_workflow(apply_migration_data=apply_migration_data, context=context)
        return await self._run_migrations_directly(apply_migration_data=apply_migration_data)

    async def _run_migrations_via_workflow(
        self,
        apply_migration_data: SchemaApplyMigrationData,
        context: InfrahubContext | None,
    ) -> tuple[list[str], Exception | None]:
        """Execute migrations via workflow service.

        Raises:
            RuntimeError: When the workflow service or context is not available.

        """
        workflow = self._get_workflow()
        if context is None:
            raise RuntimeError("Context is required but not provided")

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

    async def _rollback(self, branch: Branch, at: Timestamp) -> None:
        """Rollback all changes made at the unified timestamp."""
        rollback_query = await RollbackQuery.init(db=self.db, target_branch=branch, at=at)
        await rollback_query.execute(db=self.db)

    async def _restore_registry_state(self, branch: Branch, origin_schema: SchemaBranch) -> None:
        """Restore original schema in registry and reset branch hash."""
        self.schema_manager.set_schema_branch(name=branch.name, schema=origin_schema)
        branch.update_schema_hash()
        await branch.save(db=self.db)

    async def _handle_failure_and_rollback(
        self,
        branch: Branch,
        origin_schema: SchemaBranch,
        at: Timestamp,
        phase: str,
        exception: Exception | None,
        error_msgs: list[str],
    ) -> NoReturn:
        """Log, roll back the schema update, and raise. Never returns.

        Raises:
            MigrationError: Always raised after rollback, wrapping the original exception or aggregated error messages.

        """
        if exception:
            self.log.error(
                f"Schema {phase} failed, beginning rollback",
                extra={"branch": branch.name, "error": str(exception)},
            )
        elif error_msgs:
            self.log.error(
                f"Schema {phase} returned errors, beginning rollback",
                extra={"branch": branch.name, "errors": error_msgs},
            )
        else:
            self.log.error(
                f"Schema {phase} failed with no diagnostic information, beginning rollback",
                extra={"branch": branch.name},
            )

        await self._rollback(branch=branch, at=at)
        await self._restore_registry_state(branch=branch, origin_schema=origin_schema)
        self.log.info("Schema rollback completed", extra={"branch": branch.name})

        if exception:
            raise exception
        raise MigrationError(message=",\n".join(error_msgs))
