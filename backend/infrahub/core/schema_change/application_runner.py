from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from neo4j.exceptions import Neo4jError

from infrahub.exceptions import DatabaseError, Error, QueryError, QueryTimeoutError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.models import SchemaDiff, SchemaUpdateMigrationInfo
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.candidate import SchemaCandidate
    from infrahub.core.schema_change.operations import SchemaOperation
    from infrahub.core.schema_change.recorder import SchemaChangeRecording
    from infrahub.core.timestamp import Timestamp

log = get_logger()

RECORD_UPDATE_ERRORS = (DatabaseError, QueryError, QueryTimeoutError, Neo4jError)


class ApplicationRecorder(Protocol):
    async def start(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording: ...

    async def complete(self, *, recording: SchemaChangeRecording, branch: Branch, user_id: str) -> None: ...

    async def fail(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> None: ...


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
        application_id: str,
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

        When the update raises, the schema change is recorded as failed with the text of the error, and the same
        exception is raised again.

        Returns:
            The schema hash of the branch after the update.

        """
        recording = await self.recorder.start(branch=branch, operations=candidate.operations, at=at, user_id=user_id)
        try:
            updated_hash = await self.executor.execute(
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
                application_id=recording.application_id,
            )
        except Exception as exc:
            await self._record_failure(recording=recording, error=_error_text(exc), user_id=user_id)
            raise
        await self.recorder.complete(recording=recording, branch=branch, user_id=user_id)
        return updated_hash

    async def _record_failure(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> None:
        try:
            await self.recorder.fail(recording=recording, error=error, user_id=user_id)
        except RECORD_UPDATE_ERRORS:
            log.exception(
                "Could not record the failure of a schema change",
                schema_change_id=recording.schema_change_id,
                application_id=recording.application_id,
            )
