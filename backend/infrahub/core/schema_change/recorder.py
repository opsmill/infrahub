from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.schema_change.operations import SchemaOperation
    from infrahub.core.schema_change.repository import SchemaChangeRepository
    from infrahub.core.schema_change.version_resolver import SchemaChangeVersionResolver
    from infrahub.core.timestamp import Timestamp

EMPTY_OPERATIONS_ERROR = "A schema change needs at least one operation"


@dataclass(frozen=True)
class SchemaChangeRecording:
    schema_change_id: str
    application_id: str
    at: Timestamp
    """The timestamp of the graph writes of the application, which becomes `applied_at` of the schema change."""


class SchemaChangeRecorder:
    """Record a schema change and its application, and move both through their statuses.

    It has several entry methods because they are the steps of one schema change, each taking the
    recording that an earlier step returned. The caller holds the schema lock, so the version that
    the resolver returns is still free when it is written.
    """

    def __init__(self, repository: SchemaChangeRepository, version_resolver: SchemaChangeVersionResolver) -> None:
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
        """Set the schema change and its application to applied, with the next version of the branch and its parent."""
        version = await self.version_resolver.resolve_next(branch=branch)
        await self.repository.mark_applied(
            schema_change_id=recording.schema_change_id,
            application_id=recording.application_id,
            version=version.version,
            parent_id=version.parent_id,
            applied_at=recording.at,
            user_id=user_id,
        )

    async def fail(self, *, recording: SchemaChangeRecording, error: str, user_id: str) -> None:
        """Set the schema change and its application to failed with the error, without a version.

        The migration records that were applied become rolled back, and the others keep their status.
        """
        await self.repository.mark_failed(
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

        """
        recording = await self.start(branch=branch, operations=operations, at=at, user_id=user_id)
        await self.complete(recording=recording, branch=branch, user_id=user_id)
        return recording
