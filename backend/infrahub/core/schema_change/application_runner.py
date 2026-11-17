from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

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


class ApplicationRecorder(Protocol):
    async def start(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording: ...

    async def complete(self, *, recording: SchemaChangeRecording, branch: Branch, user_id: str) -> None: ...


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

        Returns:
            The schema hash of the branch after the update.

        """
        recording = await self.recorder.start(branch=branch, operations=candidate.operations, at=at, user_id=user_id)
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
        await self.recorder.complete(recording=recording, branch=branch, user_id=user_id)
        return updated_hash
