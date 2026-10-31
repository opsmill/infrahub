"""Data carried across the I/O boundary and the ports the decision logic talks through."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime
    from pathlib import Path


class GitHubError(Exception):
    """A GitHub read or write failed."""


class JiraError(Exception):
    """A Jira read or write failed."""


class SlackError(Exception):
    """Posting to Slack failed."""


class RunStatus(StrEnum):
    """Status shared by workflow runs and check runs; only `completed` carries a conclusion."""

    REQUESTED = "requested"
    QUEUED = "queued"
    WAITING = "waiting"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class RunConclusion(StrEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    NEUTRAL = "neutral"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    STALE = "stale"
    STARTUP_FAILURE = "startup_failure"


class CommitState(StrEnum):
    SUCCESS = "success"
    PENDING = "pending"
    FAILURE = "failure"
    ERROR = "error"


class ReviewState(StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"
    PENDING = "PENDING"


class ReviewEvent(StrEnum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


class FileStatus(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    RENAMED = "renamed"
    COPIED = "copied"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class PullRequestState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class AccountType(StrEnum):
    USER = "User"
    BOT = "Bot"
    ORGANIZATION = "Organization"


@dataclass(frozen=True)
class PullRequest:
    number: int
    html_url: str
    author_login: str
    base_ref: str
    head_sha: str
    head_repo_full_name: str | None
    """`None` when the head repository has been deleted."""
    state: PullRequestState
    merged: bool
    labels: tuple[str, ...]
    head_committed_at: datetime


@dataclass(frozen=True)
class PullRequestSummary:
    number: int
    author_login: str
    head_sha: str
    head_repo_full_name: str | None


@dataclass(frozen=True)
class Review:
    id: int
    author_login: str
    author_type: AccountType
    state: ReviewState
    commit_id: str | None
    submitted_at: datetime | None


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    name: str
    path: str
    event: str
    head_sha: str
    status: RunStatus
    conclusion: RunConclusion | None
    created_at: datetime


@dataclass(frozen=True)
class CheckRun:
    id: int
    name: str
    app_slug: str
    head_sha: str
    status: RunStatus
    conclusion: RunConclusion | None


@dataclass(frozen=True)
class CommitStatus:
    context: str
    state: CommitState


@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: FileStatus
    previous_path: str | None


@dataclass(frozen=True)
class JiraIssue:
    key: str
    summary: str
    url: str
    priority: str | None


@dataclass(frozen=True)
class JiraIssueDraft:
    project_key: str
    issue_type: str
    summary: str
    labels: tuple[str, ...]
    priority: str
    description: Mapping[str, object]
    """Atlassian Document Format document."""


class GitHubPort(Protocol):
    """GitHub reads and writes for one repository; every failure raises `GitHubError`."""

    def get_pull_request(self, *, number: int) -> PullRequest: ...

    def list_open_pull_requests(self, *, base: str) -> list[PullRequestSummary]: ...

    def list_reviews(self, *, pr_number: int) -> list[Review]: ...

    def list_workflow_runs(self, *, head_sha: str) -> list[WorkflowRun]: ...

    def list_check_runs(self, *, sha: str) -> list[CheckRun]: ...

    def list_commit_statuses(self, *, sha: str) -> list[CommitStatus]: ...

    def read_file(self, *, path: str, ref: str) -> str | None:
        """Return the file's text at `ref`, or `None` when it does not exist there."""
        ...

    def list_changed_files(self, *, pr_number: int) -> list[ChangedFile]: ...

    def list_commit_authors(self, *, pr_number: int) -> list[str | None]:
        """Return the login of each commit's author, `None` for an author not linked to a GitHub account."""
        ...

    def find_marker_comment(self, *, pr_number: int, marker: str, author_login: str) -> str | None:
        """Return the body of the comment by `author_login` containing `marker`, or `None` when there is none."""
        ...

    def upsert_marker_comment(self, *, pr_number: int, marker: str, body: str, author_login: str) -> None:
        """Edit the comment by `author_login` containing `marker`, or create one; `body` must contain `marker`."""
        ...

    def set_labels(self, *, pr_number: int, labels: list[str]) -> None:
        """Replace the full label set of the pull request."""
        ...

    def submit_review(self, *, pr_number: int, event: ReviewEvent, body: str, commit_id: str) -> None: ...

    def dismiss_review(self, *, pr_number: int, review_id: int, message: str) -> None: ...

    def request_reviewers(self, *, pr_number: int, users: list[str], teams: list[str]) -> None: ...

    def merge(self, *, pr_number: int, head_sha: str) -> None:
        """Squash-merge, refused by GitHub when the head is no longer `head_sha`."""
        ...

    def download_artifact(self, *, run_id: int, name: str, destination: Path) -> Path | None:
        """Extract the run's artifact into the empty directory `destination`.

        Returns:
            `destination`, or `None` when the run has no unexpired artifact with that name.

        """
        ...


class JiraPort(Protocol):
    """Jira reads and writes; every failure raises `JiraError`."""

    def search_open_by_label(self, *, label: str) -> list[JiraIssue]:
        """Return the issues carrying `label` whose status category is not Done."""
        ...

    def search_digest_items(
        self, *, label: str, priorities: Sequence[str], updated_within_days: int
    ) -> list[JiraIssue]:
        """Return the issues carrying `label` and one of `priorities` updated in the last `updated_within_days` days."""
        ...

    def create_issue(self, *, draft: JiraIssueDraft) -> JiraIssue: ...

    def add_comment(self, *, issue_key: str, body: Mapping[str, object]) -> None:
        """Add a comment whose `body` is an Atlassian Document Format document."""
        ...

    def list_comment_texts(self, *, issue_key: str) -> list[str]:
        """Return the plain text of every comment on the issue, link URLs included."""
        ...


class SlackPort(Protocol):
    def post_message(self, *, text: str) -> None:
        """Post `text`, raising `SlackError` on failure."""
        ...
