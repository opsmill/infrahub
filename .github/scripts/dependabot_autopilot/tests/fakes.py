"""In-memory ports that hold their state in plain fields and record every write."""

from __future__ import annotations

import dataclasses
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from dependabot_autopilot.adapters import adf_plain_text
from dependabot_autopilot.ports import (
    AccountType,
    ChangedFile,
    CheckRun,
    CommitStatus,
    GitHubError,
    JiraError,
    JiraIssue,
    JiraIssueDraft,
    PullRequest,
    PullRequestState,
    PullRequestSummary,
    Review,
    ReviewEvent,
    ReviewState,
    SlackError,
    WorkflowRun,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path


@dataclass(frozen=True)
class Comment:
    id: int
    author_login: str
    body: str


@dataclass(frozen=True)
class CommentCreated:
    pr_number: int
    body: str


@dataclass(frozen=True)
class CommentEdited:
    pr_number: int
    comment_id: int
    body: str


@dataclass(frozen=True)
class LabelsSet:
    pr_number: int
    labels: tuple[str, ...]


@dataclass(frozen=True)
class ReviewSubmitted:
    pr_number: int
    event: ReviewEvent
    body: str
    commit_id: str


@dataclass(frozen=True)
class ReviewDismissed:
    pr_number: int
    review_id: int
    message: str


@dataclass(frozen=True)
class ReviewersRequested:
    pr_number: int
    users: tuple[str, ...]
    teams: tuple[str, ...]


@dataclass(frozen=True)
class Merged:
    pr_number: int
    head_sha: str


GitHubWrite = (
    CommentCreated | CommentEdited | LabelsSet | ReviewSubmitted | ReviewDismissed | ReviewersRequested | Merged
)

_REVIEW_STATE_FOR_EVENT = {
    ReviewEvent.APPROVE: ReviewState.APPROVED,
    ReviewEvent.REQUEST_CHANGES: ReviewState.CHANGES_REQUESTED,
    ReviewEvent.COMMENT: ReviewState.COMMENTED,
}


@dataclass
class FakeGitHub:
    acting_login: str = "dependabot-autopilot[bot]"
    pull_requests: dict[int, PullRequest] = field(default_factory=dict)
    reviews: dict[int, list[Review]] = field(default_factory=dict)
    workflow_runs: list[WorkflowRun] = field(default_factory=list)
    check_runs: list[CheckRun] = field(default_factory=list)
    commit_statuses: dict[str, list[CommitStatus]] = field(default_factory=dict)
    files: dict[tuple[str, str], str] = field(default_factory=dict)
    """File text keyed by `(path, ref)`."""
    changed_files: dict[int, list[ChangedFile]] = field(default_factory=dict)
    commit_authors: dict[int, list[str | None]] = field(default_factory=dict)
    """Commit author logins per pull request; a pull request left out has one commit by its own author."""
    comments: dict[int, list[Comment]] = field(default_factory=dict)
    artifacts: dict[tuple[int, str], Path] = field(default_factory=dict)
    """Source directory copied on download, keyed by `(run_id, name)`."""
    fail_merge: bool = False
    merge_attempts: list[str] = field(default_factory=list)
    """Head SHA of every merge call, refused or not."""
    writes: list[GitHubWrite] = field(default_factory=list)
    _next_id: int = 1000

    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def get_pull_request(self, *, number: int) -> PullRequest:
        pull_request = self.pull_requests.get(number)
        if pull_request is None:
            raise GitHubError(f"pull request #{number} not found")
        return pull_request

    def list_open_pull_requests(self, *, base: str) -> list[PullRequestSummary]:
        return [
            PullRequestSummary(
                number=pull.number,
                author_login=pull.author_login,
                head_sha=pull.head_sha,
                head_repo_full_name=pull.head_repo_full_name,
            )
            for pull in self.pull_requests.values()
            if pull.state is PullRequestState.OPEN and pull.base_ref == base
        ]

    def list_reviews(self, *, pr_number: int) -> list[Review]:
        return list(self.reviews.get(pr_number, []))

    def list_workflow_runs(self, *, head_sha: str) -> list[WorkflowRun]:
        return [run for run in self.workflow_runs if run.head_sha == head_sha]

    def list_check_runs(self, *, sha: str) -> list[CheckRun]:
        return [check for check in self.check_runs if check.head_sha == sha]

    def list_commit_statuses(self, *, sha: str) -> list[CommitStatus]:
        return list(self.commit_statuses.get(sha, []))

    def read_file(self, *, path: str, ref: str) -> str | None:
        return self.files.get((path, ref))

    def list_changed_files(self, *, pr_number: int) -> list[ChangedFile]:
        return list(self.changed_files.get(pr_number, []))

    def list_commit_authors(self, *, pr_number: int) -> list[str | None]:
        if pr_number in self.commit_authors:
            return list(self.commit_authors[pr_number])
        return [self.get_pull_request(number=pr_number).author_login]

    def find_marker_comment(self, *, pr_number: int, marker: str, author_login: str) -> str | None:
        for comment in self.comments.get(pr_number, []):
            if comment.author_login == author_login and marker in comment.body:
                return comment.body
        return None

    def upsert_marker_comment(self, *, pr_number: int, marker: str, body: str, author_login: str) -> None:
        if marker not in body:
            raise ValueError("the comment body must contain the marker so the next run can find it")
        comments = self.comments.setdefault(pr_number, [])
        for index, comment in enumerate(comments):
            if comment.author_login == author_login and marker in comment.body:
                comments[index] = dataclasses.replace(comment, body=body)
                self.writes.append(CommentEdited(pr_number=pr_number, comment_id=comment.id, body=body))
                return
        comments.append(Comment(id=self._new_id(), author_login=author_login, body=body))
        self.writes.append(CommentCreated(pr_number=pr_number, body=body))

    def set_labels(self, *, pr_number: int, labels: list[str]) -> None:
        pull_request = self.get_pull_request(number=pr_number)
        self.pull_requests[pr_number] = dataclasses.replace(pull_request, labels=tuple(labels))
        self.writes.append(LabelsSet(pr_number=pr_number, labels=tuple(labels)))

    def submit_review(self, *, pr_number: int, event: ReviewEvent, body: str, commit_id: str) -> None:
        review = Review(
            id=self._new_id(),
            author_login=self.acting_login,
            author_type=AccountType.BOT,
            state=_REVIEW_STATE_FOR_EVENT[event],
            commit_id=commit_id,
            submitted_at=datetime.now(tz=UTC),
        )
        self.reviews.setdefault(pr_number, []).append(review)
        self.writes.append(ReviewSubmitted(pr_number=pr_number, event=event, body=body, commit_id=commit_id))

    def dismiss_review(self, *, pr_number: int, review_id: int, message: str) -> None:
        reviews = self.reviews.get(pr_number, [])
        for index, review in enumerate(reviews):
            if review.id == review_id:
                reviews[index] = dataclasses.replace(review, state=ReviewState.DISMISSED)
                self.writes.append(ReviewDismissed(pr_number=pr_number, review_id=review_id, message=message))
                return
        raise GitHubError(f"review {review_id} not found on #{pr_number}")

    def request_reviewers(self, *, pr_number: int, users: list[str], teams: list[str]) -> None:
        self.writes.append(ReviewersRequested(pr_number=pr_number, users=tuple(users), teams=tuple(teams)))

    def merge(self, *, pr_number: int, head_sha: str) -> None:
        self.merge_attempts.append(head_sha)
        pull_request = self.get_pull_request(number=pr_number)
        if self.fail_merge or pull_request.head_sha != head_sha:
            raise GitHubError(f"merge of #{pr_number} at {head_sha} refused")
        self.pull_requests[pr_number] = dataclasses.replace(pull_request, state=PullRequestState.CLOSED, merged=True)
        self.writes.append(Merged(pr_number=pr_number, head_sha=head_sha))

    def download_artifact(self, *, run_id: int, name: str, destination: Path) -> Path | None:
        source = self.artifacts.get((run_id, name))
        if source is None:
            return None
        shutil.copytree(src=source, dst=destination, dirs_exist_ok=True)
        return destination


@dataclass(frozen=True)
class IssueCreated:
    draft: JiraIssueDraft


@dataclass(frozen=True)
class IssueCommented:
    issue_key: str
    body: Mapping[str, object]


JiraWrite = IssueCreated | IssueCommented


@dataclass
class FakeJira:
    base_url: str = "https://jira.example.com"
    issues: dict[str, tuple[JiraIssue, tuple[str, ...]]] = field(default_factory=dict)
    """Open issues and their labels, keyed by issue key."""
    updated_days_ago: dict[str, int] = field(default_factory=dict)
    """Days since each issue was last updated; an issue left out was updated today."""
    comments: dict[str, list[str]] = field(default_factory=dict)
    """Plain text of each issue's comments, keyed by issue key."""
    unreadable_comments: set[str] = field(default_factory=set)
    """Issues whose comments cannot be read."""
    fail: bool = False
    writes: list[JiraWrite] = field(default_factory=list)
    _next_number: int = 0

    def _check_available(self) -> None:
        if self.fail:
            raise JiraError("Jira unavailable")

    def search_open_by_label(self, *, label: str) -> list[JiraIssue]:
        self._check_available()
        return [issue for issue, labels in self.issues.values() if label in labels]

    def search_digest_items(
        self, *, label: str, priorities: Sequence[str], updated_within_days: int
    ) -> list[JiraIssue]:
        self._check_available()
        return [
            issue
            for key, (issue, labels) in self.issues.items()
            if label in labels
            and issue.priority in priorities
            and self.updated_days_ago.get(key, 0) <= updated_within_days
        ]

    def create_issue(self, *, draft: JiraIssueDraft) -> JiraIssue:
        self._check_available()
        self._next_number += 1
        key = f"{draft.project_key}-{self._next_number}"
        issue = JiraIssue(key=key, summary=draft.summary, url=f"{self.base_url}/browse/{key}", priority=draft.priority)
        self.issues[key] = (issue, draft.labels)
        self.writes.append(IssueCreated(draft=draft))
        return issue

    def add_comment(self, *, issue_key: str, body: Mapping[str, object]) -> None:
        self._check_available()
        if issue_key not in self.issues:
            raise JiraError(f"issue {issue_key} not found")
        self.writes.append(IssueCommented(issue_key=issue_key, body=body))
        self.comments.setdefault(issue_key, []).append(adf_plain_text(document=body))

    def list_comment_texts(self, *, issue_key: str) -> list[str]:
        self._check_available()
        if issue_key not in self.issues or issue_key in self.unreadable_comments:
            raise JiraError(f"comments of {issue_key} unavailable")
        return list(self.comments.get(issue_key, []))


@dataclass
class FakeSlack:
    fail: bool = False
    messages: list[str] = field(default_factory=list)

    def post_message(self, *, text: str) -> None:
        if self.fail:
            raise SlackError("Slack unavailable")
        self.messages.append(text)
