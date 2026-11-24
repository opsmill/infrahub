from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.exceptions import SchemaChangeRecordNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.schema_change.operations import SchemaOperation
    from infrahub.core.schema_change.repository import CreatedSchemaChange
    from infrahub.core.schema_change.version_resolver import SchemaChangeVersionResolver
    from infrahub.core.timestamp import Timestamp

EMPTY_OPERATIONS_ERROR = "A schema change needs at least one operation"


class SchemaChangeRecordStore(Protocol):
    async def create_schema_change(
        self, *, branch: str, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> CreatedSchemaChange: ...

    async def mark_applied(
        self,
        *,
        schema_change_id: str,
        application_id: str,
        version: int,
        parent_id: str | None,
        applied_at: Timestamp,
        user_id: str,
    ) -> bool: ...

    async def mark_failed(self, *, schema_change_id: str, application_id: str, error: str, user_id: str) -> bool: ...

    async def mark_failed_if_running(
        self, *, schema_change_id: str, application_id: str, error: str, user_id: str
    ) -> bool: ...


@dataclass(frozen=True)
class SchemaChangeRecording:
    schema_change_id: str
    application_id: str
    at: Timestamp
    """The timestamp of the graph writes of the application, which becomes `applied_at` of the schema change."""


class SchemaChangeRecorder:
    """Record a schema change and its application, and move both through their statuses.

    The caller must hold the schema lock while a step writes the next version of the branch.
    """

    def __init__(self, repository: SchemaChangeRecordStore, version_resolver: SchemaChangeVersionResolver) -> None:
        self.repository = repository
        self.version_resolver = version_resolver

    async def start(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording:
        """Create a running schema change without a version, and its running application.

        Raises:
            ValueError: When `operations` is empty; nothing is stored.

        """
        if not operations:
            raise ValueError(EMPTY_OPERATIONS_ERROR)

        created = await self.repository.create_schema_change(
            branch=branch.name, operations=operations, at=at, user_id=user_id
        )
        return SchemaChangeRecording(
            schema_change_id=created.schema_change_id, application_id=created.application_id, at=at
        )

    async def complete(self, *, recording: SchemaChangeRecording, branch: Branch, user_id: str) -> None:
        """Set the schema change and its application to applied, with the next version of the branch and its parent.

        Raises:
            SchemaChangeRecordNotFoundError: When the schema change, its application or the parent is no longer stored.

        """
        version = await self.version_resolver.resolve_next(branch=branch)
        applied = await self.repository.mark_applied(
            schema_change_id=recording.schema_change_id,
            application_id=recording.application_id,
            version=version.version,
            parent_id=version.parent_id,
            applied_at=recording.at,
            user_id=user_id,
        )
        if not applied:
            raise SchemaChangeRecordNotFoundError(schema_change_id=recording.schema_change_id)

    async def fail(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> bool:
        """Set the schema change and its application to failed with the error, without a version.

        An applied migration record becomes rolled back, a waiting one cancelled, and a running one failed with the
        error added to its errors; a failed one stays failed.

        Returns:
            Whether the schema change was set to failed; False when its records are no longer stored.

        """
        return await self.repository.mark_failed(
            schema_change_id=recording.schema_change_id,
            application_id=recording.application_id,
            error=error,
            user_id=user_id,
        )

    async def fail_if_running(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> bool:
        """Set the schema change and its application to failed with the error, only while the schema change is running.

        It is for a cancelled load, whose migrations keep running and write their own statuses, so it leaves the
        migration records as they are.

        Returns:
            Whether the schema change was set to failed; False when it was already recorded as applied or failed.

        """
        return await self.repository.mark_failed_if_running(
            schema_change_id=recording.schema_change_id,
            application_id=recording.application_id,
            error=error,
            user_id=user_id,
        )

    async def record_applied(
        self, *, branch: Branch, operations: Sequence[SchemaOperation], at: Timestamp, user_id: str
    ) -> SchemaChangeRecording:
        """Create an applied schema change, with the next version of the branch and its parent, and its applied application.

        Raises:
            ValueError: When `operations` is empty; nothing is stored.
            SchemaChangeRecordNotFoundError: When the created records are deleted before they are set to applied.

        """
        recording = await self.start(branch=branch, operations=operations, at=at, user_id=user_id)
        await self.complete(recording=recording, branch=branch, user_id=user_id)
        return recording
