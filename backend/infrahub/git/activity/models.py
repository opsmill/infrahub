"""The activity records a repository run keeps in the cache, shared by the git workers and the API resolver."""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel

from infrahub.utils import InfrahubStringEnum


class RepositoryActivityOperation(InfrahubStringEnum):
    SYNC = "sync"
    REIMPORT = "reimport"
    PULL = "pull"
    ADD = "add"
    BRANCH_CREATE = "branch_create"
    MERGE = "merge"


class RepositoryActivityPhase(InfrahubStringEnum):
    FETCHING = "fetching"
    BUILDING = "building"
    APPLYING = "applying"


class RepositoryActivityBranchOutcome(InfrahubStringEnum):
    IMPORTED = "imported"
    FAILED = "failed"


class ActivityRunRecord(BaseModel):
    """A run that is working on a repository now, as one worker last wrote it."""

    run_id: str
    repository_id: str
    operation: RepositoryActivityOperation
    phase: RepositoryActivityPhase | None
    branch_name: str | None
    """Null while fetching, because a fetch covers every branch."""

    worker_id: str
    started_at: AwareDatetime
    updated_at: AwareDatetime


class ActivityBranchRecord(BaseModel):
    branch_name: str
    outcome: RepositoryActivityBranchOutcome


class LastRunRecord(BaseModel):
    """The most recent finished run of one operation on a repository."""

    operation: RepositoryActivityOperation
    started_at: AwareDatetime
    finished_at: AwareDatetime
    branches: list[ActivityBranchRecord]
    """The branches the run changed or failed on."""
