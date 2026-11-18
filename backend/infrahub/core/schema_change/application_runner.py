from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from infrahub.core.schema_change.record_errors import RECORD_WRITE_ERRORS
from infrahub.exceptions import Error
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.models import SchemaDiff, SchemaUpdateMigrationInfo
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema.update_coordinator import SchemaUpdateFinalStep
    from infrahub.core.schema_change.candidate import SchemaCandidate
    from infrahub.core.schema_change.operations import SchemaOperation
    from infrahub.core.schema_change.recorder import SchemaChangeRecording
    from infrahub.core.timestamp import Timestamp

log = get_logger()

LOAD_CANCELLED_ERROR = "The schema load was cancelled before it completed"


class ApplicationRecorder(Protocol):
    async def start(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording: ...

    async def complete(self, *, recording: SchemaChangeRecording, branch: Branch, user_id: str) -> None: ...

    async def fail(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> None: ...

    async def fail_if_running(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> bool: ...


class SchemaUpdateExecutor(Protocol):
    async def execute(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        rollback_schema: SchemaBranch,
        candidate_schema: SchemaBranch,
        at: Timestamp,
        context: InfrahubContext,
        diff: SchemaDiff,
        migrations: list[SchemaUpdateMigrationInfo],
        limit: list[str],
        user_id: str,
        application_id: str | None,
        final_step: SchemaUpdateFinalStep | None,
    ) -> str: ...


def _error_text(exc: Exception) -> str:
    # An Infrahub error can hold its text in `message` alone, which leaves `str()` empty.
    if isinstance(exc, Error) and exc.message:
        return exc.message
    return str(exc)


class SchemaChangeApplicationRunner:
    """Apply a candidate schema to a branch as a new schema change, and keep its records in step with the result."""

    def __init__(self, recorder: ApplicationRecorder, executor: SchemaUpdateExecutor) -> None:
        self.recorder = recorder
        self.executor = executor

    async def run(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        candidate: SchemaCandidate,
        at: Timestamp,
        context: InfrahubContext,
        user_id: str,
    ) -> str:
        """Record a running schema change, apply the candidate at `at`, then record the schema change as applied.

        The schema change is recorded as applied as the last step of the update, so a failure to record it rolls the
        update back. When the update raises, the schema change is recorded as failed with the text of the error, and
        the same exception is raised again; a failure to record that is logged. When the load is cancelled, a schema
        change that is still running is recorded as failed in a write that the cancellation does not stop, then the
        cancellation goes on; one already recorded as applied keeps that status.

        A candidate without operations is applied without storing a schema change, and a warning names the branch.

        Returns:
            The schema hash of the branch after the update.

        Raises:
            CancelledError: When the load is cancelled, after a schema change that is still running is recorded as
                failed.

        """
        if not candidate.operations:
            # A schema change needs an operation, and a load must not fail because its operations missed a change.
            log.warning(
                "Applying a schema change that has no operation, without recording it",
                branch=branch.name,
                diff=candidate.validation.diff.all,
            )
            return await self._execute(
                branch=branch,
                origin_schema=origin_schema,
                candidate=candidate,
                at=at,
                context=context,
                user_id=user_id,
                application_id=None,
                final_step=None,
            )

        recording = await self.recorder.start(branch=branch, operations=candidate.operations, at=at, user_id=user_id)

        async def record_completion() -> None:
            await self.recorder.complete(recording=recording, branch=branch, user_id=user_id)

        try:
            return await self._execute(
                branch=branch,
                origin_schema=origin_schema,
                candidate=candidate,
                at=at,
                context=context,
                user_id=user_id,
                application_id=recording.application_id,
                final_step=record_completion,
            )
        except asyncio.CancelledError:
            await asyncio.shield(self._record_cancellation(recording=recording, user_id=user_id))
            raise
        except Exception as exc:
            await self._record_failure(recording=recording, error=_error_text(exc), user_id=user_id)
            raise

    async def _execute(
        self,
        *,
        branch: Branch,
        origin_schema: SchemaBranch,
        candidate: SchemaCandidate,
        at: Timestamp,
        context: InfrahubContext,
        user_id: str,
        application_id: str | None,
        final_step: SchemaUpdateFinalStep | None,
    ) -> str:
        return await self.executor.execute(
            branch=branch,
            origin_schema=origin_schema,
            rollback_schema=origin_schema,
            candidate_schema=candidate.schema,
            at=at,
            context=context,
            diff=candidate.validation.diff,
            migrations=candidate.validation.migrations,
            limit=candidate.validation.diff.all,
            user_id=user_id,
            application_id=application_id,
            final_step=final_step,
        )

    async def _record_cancellation(self, *, recording: SchemaChangeRecording, user_id: str) -> None:
        # The cancellation can arrive after the schema change was recorded as applied, and a cancelled load does not
        # roll back the schema, so only a schema change that is still running is recorded as failed.
        try:
            recorded = await self.recorder.fail_if_running(
                recording=recording, error=LOAD_CANCELLED_ERROR, user_id=user_id
            )
        except RECORD_WRITE_ERRORS:
            log.exception(
                "Could not record the failure of a schema change",
                schema_change_id=recording.schema_change_id,
                application_id=recording.application_id,
            )
            return
        if not recorded:
            log.warning(
                "The schema load was cancelled after its schema change stopped running, so its status is kept",
                schema_change_id=recording.schema_change_id,
                application_id=recording.application_id,
            )

    async def _record_failure(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> None:
        try:
            await self.recorder.fail(recording=recording, error=error, user_id=user_id)
        except RECORD_WRITE_ERRORS:
            log.exception(
                "Could not record the failure of a schema change",
                schema_change_id=recording.schema_change_id,
                application_id=recording.application_id,
            )
