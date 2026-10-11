from datetime import date, datetime
from enum import StrEnum
from typing import assert_never

from pydantic import BaseModel, ConfigDict, Field


class CleanupJobState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CleanupRewrite(StrEnum):
    """Whether a cleanup rewrites tables after its deletes; nothing is rewritten on SQLite."""

    NEVER = "never"
    IF_FREED = "if_freed"
    """Each task history and activity log table whose live rows hold less than half of its disk space, whoever freed it."""

    @property
    def strength(self) -> int:
        """Rank of the mode, which rewrites the tables whenever a mode of a lower rank would."""
        match self:
            case CleanupRewrite.NEVER:
                strength = 0
            case CleanupRewrite.IF_FREED:
                strength = 1
            case _:
                assert_never(self)
        return strength


class CleanupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rewrite: CleanupRewrite = Field(
        default=CleanupRewrite.NEVER, description="Whether to rewrite tables after the deletes"
    )


class CleanupJob(BaseModel):
    id: str
    state: CleanupJobState
    rewrite: CleanupRewrite = Field(
        description="Whether to rewrite tables after the deletes, raised by a request for a stronger mode while it runs"
    )
    cutoff: datetime = Field(description="Runs that ended before this time are deleted")
    deleted_runs: int = 0
    current_day: date | None = Field(default=None, description="Day of end times being deleted")
    size_before: int | None = Field(
        default=None,
        description="Total size in bytes of the tables a cleanup may rewrite, before the deletes, on Postgres",
    )
    size_after: int | None = Field(
        default=None, description="Total size in bytes of the tables a cleanup may rewrite, at the end, on Postgres"
    )
    rewritten: list[str] = Field(default_factory=list, description="Tables rewritten")
    mostly_live: list[str] = Field(
        default_factory=list,
        description="Tables left as they are, because their live rows hold at least half of their disk space",
    )
    not_rewritten: list[str] = Field(
        default_factory=list, description="Tables whose rewrite still waited too long for a lock after its retries"
    )
    error: str | None = None


class TaskHistorySize(BaseModel):
    size: int | None = Field(
        description="Disk space in bytes of the task history tables with their indexes, or None on SQLite"
    )
