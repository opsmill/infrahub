from datetime import date, datetime
from enum import StrEnum
from typing import assert_never

from pydantic import BaseModel, ConfigDict, Field


class CleanupJobState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CleanupRewrite(StrEnum):
    """When a cleanup rewrites the task history tables after its deletes; nothing is rewritten on SQLite."""

    NEVER = "never"
    IF_FREED = "if_freed"
    """When the deletes, including the task manager's own meanwhile, freed more than half of the runs."""
    ALWAYS = "always"

    @property
    def strength(self) -> int:
        """Rank of the mode, which rewrites the tables whenever a mode of a lower rank would."""
        match self:
            case CleanupRewrite.NEVER:
                strength = 0
            case CleanupRewrite.IF_FREED:
                strength = 1
            case CleanupRewrite.ALWAYS:
                strength = 2
            case _:
                assert_never(self)
        return strength


class CleanupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rewrite: CleanupRewrite = Field(
        default=CleanupRewrite.NEVER, description="When to rewrite the task history tables after the deletes"
    )


class CleanupJob(BaseModel):
    id: str
    state: CleanupJobState
    rewrite: CleanupRewrite = Field(
        description="When to rewrite the tables after the deletes, raised by a request for a stronger mode while it runs"
    )
    rewritten: bool = Field(
        default=False, description="Whether the tables were rewritten, which never happens on SQLite"
    )
    cutoff: datetime = Field(description="Runs that ended before this time are deleted")
    deleted_runs: int = 0
    current_day: date | None = Field(default=None, description="Day of end times being deleted")
    size_before: int | None = Field(
        default=None, description="Total size in bytes of the task history tables before the deletes, on Postgres"
    )
    size_after: int | None = Field(
        default=None, description="Total size in bytes of the task history tables at the end, on Postgres"
    )
    not_rewritten: list[str] = Field(
        default_factory=list, description="Tables whose rewrite still waited too long for a lock after its retries"
    )
    error: str | None = None
