from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema_change.repository import AppliedSchemaChangeVersion

FIRST_SCHEMA_CHANGE_VERSION = 1
"""The version of the first applied schema change of a branch that starts from no applied schema change."""


class AppliedVersionReader(Protocol):
    async def get_highest_applied_version(self, *, branch: str) -> AppliedSchemaChangeVersion | None: ...

    async def get_highest_applied_version_at(
        self, *, branch: str, at: Timestamp
    ) -> AppliedSchemaChangeVersion | None: ...


@dataclass(frozen=True)
class SchemaChangeVersion:
    version: int
    parent_id: str | None


class SchemaChangeVersionResolver:
    """Calculate the version and the parent of the next applied schema change of a branch.

    The caller holds the schema lock, so the result is still correct when the caller writes it.
    """

    def __init__(self, repository: AppliedVersionReader, default_branch_name: str) -> None:
        self.repository = repository
        self.default_branch_name = default_branch_name

    async def resolve_next(self, *, branch: Branch) -> SchemaChangeVersion:
        """Return the version that follows the last applied schema change of the branch, or of main when the branch was created."""
        latest = await self.repository.get_highest_applied_version(branch=branch.name)
        if latest is not None:
            return SchemaChangeVersion(version=latest.version + 1, parent_id=latest.schema_change_id)

        if branch.name != self.default_branch_name and branch.branched_from is not None:
            base = await self.repository.get_highest_applied_version_at(
                branch=self.default_branch_name, at=Timestamp(branch.branched_from)
            )
            if base is not None:
                return SchemaChangeVersion(version=base.version + 1, parent_id=base.schema_change_id)

        return SchemaChangeVersion(version=FIRST_SCHEMA_CHANGE_VERSION, parent_id=None)
