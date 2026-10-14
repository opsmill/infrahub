from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import DateTime, Enum, Field, Int, List, NonNull, ObjectType, String

from infrahub.core import constants
from infrahub.git.activity import models as activity_models

if TYPE_CHECKING:
    from collections.abc import Callable

RepositoryGitCondition = Enum.from_enum(
    constants.RepositoryGitCondition,
    description="How the remote head relates to the commit Infrahub has imported on the request branch.",
)

RepositoryCommitState = Enum.from_enum(
    constants.RepositoryCommitState,
    description="Explicit state of one commit relative to the imported commit and the remote head.",
)

RepositoryGitUnavailableReason = Enum.from_enum(
    constants.RepositoryGitUnavailableReason, description="Why no git-derived answer was produced."
)


class RepositoryCommit(ObjectType):
    """A commit read live from a worker's local clone. Never persisted."""

    hash = String(required=True, description="Full commit hash.")
    short_hash = String(required=True, description="First 7 characters of the hash.")
    summary = String(required=True, description="First line of the commit message.")
    message = String(required=True, description="Full commit message.")
    author_name = String(required=True)
    authored_at = DateTime(required=True)
    committed_at = DateTime(required=True)
    state = RepositoryCommitState(required=True)


class RepositoryCommitNode(ObjectType):
    node = Field(RepositoryCommit, required=True)


class RepositoryGitUnavailable(ObjectType):
    """Set when condition is UNAVAILABLE. Distinct from an error: the request succeeded, git had no answer yet."""

    reason = RepositoryGitUnavailableReason(required=True)
    message = String(required=True, description="Human-readable explanation safe to display.")


class RepositoryCommits(ObjectType):
    """Commit log of a repository as seen from the request branch, newest first."""

    repository_id = String(required=True)
    branch_name = String(required=True, description="The Infrahub branch the answer was computed for.")
    git_ref = String(
        description="Remote branch or tracked ref whose history is listed. Null when the branch tracks nothing, "
        "matching RepositoryBranchDrift.git_ref."
    )
    condition = RepositoryGitCondition(required=True)
    imported_commit = String(
        description="Commit Infrahub has imported on this branch, from the repository's commit attribute."
    )
    remote_head = String(
        description="Head of the remote branch or tracked ref as last fetched by the answering worker."
    )
    pending_count = Int(
        description="Number of commits between imported_commit and remote_head. Only set when condition is BEHIND."
    )
    fetched_at = DateTime(
        description="When the answering worker last fetched from the remote. Null before the first fetch, and after a failed fetch."
    )
    checked_at = DateTime(
        description="When the remote was last checked for movement. Read-only repositories only; null for "
        "read-write, where fetched_at already carries it."
    )
    unavailable = Field(RepositoryGitUnavailable)
    edges = List(NonNull(RepositoryCommitNode), required=True)


class RepositoryBranchDrift(ObjectType):
    """Drift of one Infrahub branch of a repository."""

    branch_name = String(required=True)
    git_ref = String(
        description="Remote branch or tracked ref compared for this branch. Null when the branch is not tracked."
    )
    tracked_commit = String()
    remote_head = String(
        description="Latest remote commit. Null when there is no remote counterpart or when condition is UNAVAILABLE."
    )
    condition = RepositoryGitCondition(required=True)


class RepositoryBranchDriftNode(ObjectType):
    node = Field(RepositoryBranchDrift, required=True)


class RepositoryBranchDrifts(ObjectType):
    """Drift for every branch of a repository, produced by a single worker request."""

    repository_id = String(required=True)
    fetched_at = DateTime()
    checked_at = DateTime(description="When the remote was last checked for movement. Read-only repositories only.")
    unavailable = Field(
        RepositoryGitUnavailable,
        description="Set when the git-derived drift answer could not be produced. It does not suppress edges, "
        "which is resolved separately.",
    )
    edges = List(
        NonNull(RepositoryBranchDriftNode),
        required=True,
        description="One row per open branch the caller may view, and for a read-write repository only those "
        "synchronised with Git. The set is the branch list as it stands now: an `at` in the past changes the "
        "values each row reports, never which branches are listed.",
    )


def _value_descriptions(type_description: str, values: dict[Any, str]) -> Callable[[Any], str]:
    """Return the description callable graphene calls with each enum value, and with None for the type."""

    def describe(value: Any) -> str:
        if value is None:
            return type_description
        return values[value]

    return describe


RepositoryActivityOperation = Enum.from_enum(
    activity_models.RepositoryActivityOperation,
    description=_value_descriptions(
        type_description="Operation that a repository run performs.",
        values={
            activity_models.RepositoryActivityOperation.SYNC: (
                "Periodic check of every tracked branch for new commits, and import of those commits."
            ),
            activity_models.RepositoryActivityOperation.REIMPORT: "Import of one branch requested by a user.",
            activity_models.RepositoryActivityOperation.PULL: (
                "Import of the latest commit of the ref a read-only repository tracks."
            ),
            activity_models.RepositoryActivityOperation.ADD: "First clone and import after the repository was added.",
            activity_models.RepositoryActivityOperation.BRANCH_CREATE: (
                "Creation of the git branch for a new Infrahub branch."
            ),
            activity_models.RepositoryActivityOperation.MERGE: "Merge of a branch's git changes into its target branch.",
        },
    ),
)

RepositoryActivityPhase = Enum.from_enum(
    activity_models.RepositoryActivityPhase,
    description=_value_descriptions(
        type_description="Step of a run.",
        values={
            activity_models.RepositoryActivityPhase.FETCHING: "Fetching from the remote. Covers every branch.",
            activity_models.RepositoryActivityPhase.BUILDING: (
                "Reading and validating the repository files for one branch."
            ),
            activity_models.RepositoryActivityPhase.APPLYING: (
                "Writing the imported objects to Infrahub for one branch."
            ),
        },
    ),
)

RepositoryActivityBranchOutcome = Enum.from_enum(
    activity_models.RepositoryActivityBranchOutcome,
    description=_value_descriptions(
        type_description="Result of a run for one branch.",
        values={
            activity_models.RepositoryActivityBranchOutcome.IMPORTED: (
                "The run changed the branch: it imported objects into it, created it in Git, or merged into it."
            ),
            activity_models.RepositoryActivityBranchOutcome.FAILED: (
                "The run failed on this branch. The task log shows why."
            ),
        },
    ),
)


class RepositoryActivityRunNode(ObjectType):
    """A run that is working on a repository now."""

    run_id = String(required=True, description="Identifier of the run, unique while the run is active.")
    operation = RepositoryActivityOperation(required=True, description="What the run is doing.")
    phase = RepositoryActivityPhase(
        description="Step the run is in. Null until the run reports its first step, and for an operation without "
        "separate steps."
    )
    branch_name = String(
        description="Infrahub branch being built or applied. Null while fetching, because a fetch covers every branch."
    )
    worker_id = String(required=True, description="Worker running the run, as listed by InfrahubStatus.")
    started_at = DateTime(required=True, description="When the run started, by the worker's clock.")
    updated_at = DateTime(required=True, description="When the worker last confirmed that the run is still active.")


class RepositoryActivityRunEdge(ObjectType):
    """One entry in the list of active runs."""

    node = Field(RepositoryActivityRunNode, required=True, description="One active run.")


class RepositoryActivityRuns(ObjectType):
    """The runs working on a repository now."""

    edges = List(NonNull(RepositoryActivityRunEdge), required=True, description="The active runs, oldest first.")


class RepositoryActivityBranchNode(ObjectType):
    """The result of a run for one branch."""

    branch_name = String(required=True, description="Infrahub branch.")
    outcome = RepositoryActivityBranchOutcome(required=True, description="Result of the run for this branch.")


class RepositoryActivityBranchEdge(ObjectType):
    """One entry in the list of branch results."""

    node = Field(RepositoryActivityBranchNode, required=True, description="One branch result.")


class RepositoryActivityBranches(ObjectType):
    """The branches the run changed or failed on."""

    edges = List(NonNull(RepositoryActivityBranchEdge), required=True, description="The branch results of the run.")


class RepositoryActivityLastRunNode(ObjectType):
    """The most recent finished run of one operation."""

    operation = RepositoryActivityOperation(required=True, description="What the run did.")
    started_at = DateTime(required=True, description="When the run started, by the worker's clock.")
    finished_at = DateTime(required=True, description="When the run ended, whether it succeeded or failed.")
    branches = Field(
        RepositoryActivityBranches,
        required=True,
        description="Branches that the run changed or failed on. Branches without a change are left out.",
    )


class RepositoryActivityLastRunEdge(ObjectType):
    """One entry in the list of last runs."""

    node = Field(RepositoryActivityLastRunNode, required=True, description="The last run of one operation.")


class RepositoryActivityLastRuns(ObjectType):
    """The most recent finished run of each operation."""

    edges = List(
        NonNull(RepositoryActivityLastRunEdge), required=True, description="One last run per operation, newest first."
    )


class RepositoryActivityLock(ObjectType):
    """The holder of a repository lock."""

    worker_id = String(required=True, description="Worker holding the lock, as listed by InfrahubStatus.")
    requested_at = DateTime(
        description="When the worker asked for the lock, by its clock. It can have waited for the lock after that. "
        "Null when it cannot be read."
    )


class RepositoryActivity(ObjectType):
    """What is running on a repository now, across every branch."""

    repository_id = String(required=True, description="ID of the repository the answer is for.")
    active_runs = Field(
        RepositoryActivityRuns,
        required=True,
        description="Runs working on this repository now. Empty when nothing is running. A run whose worker "
        "stopped without cleaning up disappears within 5 minutes.",
    )
    last_runs = Field(
        RepositoryActivityLastRuns,
        required=True,
        description="The most recent finished run of each operation in the last 30 days, newest first.",
    )
    lock = Field(
        RepositoryActivityLock,
        description="Holder of the repository lock. Null when the lock is not held. Short tasks such as fetches "
        "also hold the lock, so a held lock does not mean that a run is active.",
    )
