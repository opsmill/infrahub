from __future__ import annotations

import re
from enum import Enum
from typing import List

from infrahub_sdk.client import NodeDiff  # noqa: TCH002
from pydantic import BaseModel, Field

SCHEMA_CHANGE = re.compile("^Schema[A-Z]")


class MessageTTL(int, Enum):
    """Defines the message TTL in seconds, the values themselves are in milliseconds."""

    FIVE = 5000
    TEN = 10000
    TWENTY = 20000

    @classmethod
    def variations(cls) -> List[MessageTTL]:
        """Return available variations of message time to live."""
        return [cls(cls.__members__[member].value) for member in list(cls.__members__)]


class ProposedChangeRepository(BaseModel):
    repository_id: str
    repository_name: str
    read_only: bool
    source_branch: str
    destination_branch: str
    source_commit: str = Field(default="")
    destination_commit: str = Field(default="")
    conflicts: List[str] = Field(default_factory=list, description="List of files with merge conflicts")
    files_added: List[str] = Field(default_factory=list)
    files_changed: List[str] = Field(default_factory=list)
    files_removed: List[str] = Field(default_factory=list)

    @property
    def has_diff(self) -> bool:
        """Indicates if a diff exists for managed repositories."""
        if not self.read_only and self.source_commit and self.source_commit != self.destination_commit:
            return True
        return False


class ProposedChangeBranchDiff(BaseModel):
    diff_summary: list[NodeDiff] = Field(default_factory=list, description="The DiffSummary between two branches")
    repositories: list[ProposedChangeRepository] = Field(default_factory=list)

    def has_node_changes(self, branch: str) -> bool:
        """Indicates if there is at least one node object that has been modified in the branch"""
        return bool(
            [
                entry
                for entry in self.diff_summary
                if entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"])
            ]
        )

    def has_data_changes(self, branch: str) -> bool:
        """Indicates if there are node or schema changes within the branch."""
        return bool([entry for entry in self.diff_summary if entry["branch"] == branch])
