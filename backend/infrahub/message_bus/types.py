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


class ProposedChangeBranchDiff(BaseModel):
    diff_summary: list[NodeDiff] = Field(default_factory=list, description="The DiffSummary between two branches")

    def has_data_changes(self, branch: str) -> bool:
        return bool(
            [
                entry
                for entry in self.diff_summary
                if entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"])
            ]
        )

    def has_schema_changes(self, branch: str) -> bool:
        return bool(
            [entry for entry in self.diff_summary if entry["branch"] == branch and SCHEMA_CHANGE.match(entry["kind"])]
        )
