from __future__ import annotations

from graphene import DateTime, Enum, Field, Int, List, NonNull, ObjectType, String

from infrahub.core import constants

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
    warm_up_task_id = String(description="Task id of the warm-up that was started, when one was.")


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
        description="When the answering worker last fetched from the remote. Null before the first fetch."
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
        description="Latest remote commit. Null when there is no remote counterpart or the branch is not tracked."
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
        description="Set when the git-derived drift answer could not be produced. It does not empty edges, "
        "whose rows are graph-resolved and unaffected.",
    )
    edges = List(NonNull(RepositoryBranchDriftNode), required=True)
