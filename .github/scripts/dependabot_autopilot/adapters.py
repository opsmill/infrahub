"""Port implementations over external tools and services."""

from __future__ import annotations

import base64
import json
import re
import subprocess  # noqa: S404
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import quote

from dependabot_autopilot.ports import (
    AccountType,
    ChangedFile,
    CheckRun,
    CommitState,
    CommitStatus,
    FileStatus,
    GitHubError,
    JiraError,
    JiraIssue,
    PullRequest,
    PullRequestState,
    PullRequestSummary,
    Review,
    ReviewEvent,
    ReviewState,
    RunConclusion,
    RunStatus,
    SlackError,
    WorkflowRun,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence
    from pathlib import Path

    from dependabot_autopilot.ports import JiraIssueDraft

PER_PAGE = 100
_RAW_CONTENT = "Accept: application/vnd.github.raw+json"
JIRA_PAGE_SIZE = 50
HTTP_TIMEOUT_SECONDS = 30
_MAX_ERROR_BODY_CHARS = 500
_JIRA_LABEL = re.compile(r"[A-Za-z0-9_.-]+")
_JIRA_ISSUE_KEY = re.compile(r"[A-Z][A-Z0-9_]*-[0-9]+")
_JIRA_PRIORITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]*")


class GhCommandError(GitHubError):
    """A `gh` invocation exited non-zero."""

    def __init__(self, *, args: list[str], stderr: str) -> None:
        super().__init__(f"gh {' '.join(args)} failed: {stderr.strip()}")
        self.stderr = stderr

    @property
    def not_found(self) -> bool:
        return "HTTP 404" in self.stderr


class GhRunner(Protocol):
    def __call__(self, *, args: Sequence[str], stdin: str | None = None) -> str:
        """Run `gh` with `args` and return its standard output, raising `GhCommandError` on failure."""
        ...


def run_gh(*, args: Sequence[str], stdin: str | None = None) -> str:
    """Run the `gh` CLI, authenticated through the `GH_TOKEN` environment variable.

    Raises:
        GhCommandError: When `gh` exits non-zero.

    """
    completed = subprocess.run(  # noqa: S603
        ["gh", *args],  # noqa: S607
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise GhCommandError(args=list(args), stderr=completed.stderr)
    return completed.stdout


@dataclass(frozen=True)
class GhCliGitHub:
    """GitHub port for one repository over `gh api`; unknown enum values in responses raise `ValueError`."""

    repo: str
    runner: GhRunner = run_gh

    def get_pull_request(self, *, number: int) -> PullRequest:
        pull = self._get(path=f"repos/{self.repo}/pulls/{number}")
        head_sha = pull["head"]["sha"]
        commit = self._get(path=f"repos/{self.repo}/commits/{head_sha}")
        head_repo = pull["head"]["repo"]
        return PullRequest(
            number=pull["number"],
            html_url=pull["html_url"],
            author_login=pull["user"]["login"],
            base_ref=pull["base"]["ref"],
            head_sha=head_sha,
            head_repo_full_name=None if head_repo is None else head_repo["full_name"],
            state=PullRequestState(pull["state"]),
            merged=bool(pull["merged"]),
            labels=tuple(label["name"] for label in pull["labels"]),
            head_committed_at=_timestamp(value=commit["commit"]["committer"]["date"]),
        )

    def list_open_pull_requests(self, *, base: str) -> list[PullRequestSummary]:
        return [
            PullRequestSummary(
                number=pull["number"],
                author_login=pull["user"]["login"],
                head_sha=pull["head"]["sha"],
                head_repo_full_name=None if pull["head"]["repo"] is None else pull["head"]["repo"]["full_name"],
            )
            for pull in self._paginate(path=f"repos/{self.repo}/pulls?state=open&base={quote(base, safe='')}")
        ]

    def list_reviews(self, *, pr_number: int) -> list[Review]:
        return [
            Review(
                id=review["id"],
                author_login=review["user"]["login"],
                author_type=AccountType(review["user"]["type"]),
                state=ReviewState(review["state"]),
                commit_id=review.get("commit_id"),
                submitted_at=None if review.get("submitted_at") is None else _timestamp(value=review["submitted_at"]),
            )
            for review in self._paginate(path=f"repos/{self.repo}/pulls/{pr_number}/reviews")
        ]

    def list_workflow_runs(self, *, head_sha: str) -> list[WorkflowRun]:
        return [
            WorkflowRun(
                id=run["id"],
                name=run["name"],
                path=run["path"],
                event=run["event"],
                head_sha=run["head_sha"],
                status=RunStatus(run["status"]),
                conclusion=_conclusion(value=run["conclusion"]),
                created_at=_timestamp(value=run["created_at"]),
            )
            for run in self._paginate(path=f"repos/{self.repo}/actions/runs?head_sha={head_sha}", key="workflow_runs")
        ]

    def list_check_runs(self, *, sha: str) -> list[CheckRun]:
        return [
            CheckRun(
                id=check["id"],
                name=check["name"],
                app_slug=check["app"]["slug"],
                head_sha=check["head_sha"],
                status=RunStatus(check["status"]),
                conclusion=_conclusion(value=check["conclusion"]),
            )
            for check in self._paginate(path=f"repos/{self.repo}/commits/{sha}/check-runs", key="check_runs")
        ]

    def list_commit_statuses(self, *, sha: str) -> list[CommitStatus]:
        return [
            CommitStatus(context=status["context"], state=CommitState(status["state"]))
            for status in self._paginate(path=f"repos/{self.repo}/commits/{sha}/status", key="statuses")
        ]

    def read_file(self, *, path: str, ref: str) -> str | None:
        try:
            return self.runner(
                args=["api", "-H", _RAW_CONTENT, f"repos/{self.repo}/contents/{quote(path)}?ref={quote(ref, safe='')}"]
            )
        except GhCommandError as exc:
            if exc.not_found:
                return None
            raise

    def list_changed_files(self, *, pr_number: int) -> list[ChangedFile]:
        return [
            ChangedFile(
                path=changed["filename"],
                status=FileStatus(changed["status"]),
                previous_path=changed.get("previous_filename"),
            )
            for changed in self._paginate(path=f"repos/{self.repo}/pulls/{pr_number}/files")
        ]

    def find_marker_comment(self, *, pr_number: int, marker: str, author_login: str) -> str | None:
        comment = self._marker_comment(pr_number=pr_number, marker=marker, author_login=author_login)
        return None if comment is None else comment["body"]

    def upsert_marker_comment(self, *, pr_number: int, marker: str, body: str, author_login: str) -> None:
        if marker not in body:
            raise ValueError("the comment body must contain the marker so the next run can find it")
        comment = self._marker_comment(pr_number=pr_number, marker=marker, author_login=author_login)
        if comment is None:
            self._send(method="POST", path=f"repos/{self.repo}/issues/{pr_number}/comments", payload={"body": body})
        else:
            self._send(
                method="PATCH", path=f"repos/{self.repo}/issues/comments/{comment['id']}", payload={"body": body}
            )

    def set_labels(self, *, pr_number: int, labels: list[str]) -> None:
        self._send(method="PUT", path=f"repos/{self.repo}/issues/{pr_number}/labels", payload={"labels": labels})

    def submit_review(self, *, pr_number: int, event: ReviewEvent, body: str, commit_id: str) -> None:
        self._send(
            method="POST",
            path=f"repos/{self.repo}/pulls/{pr_number}/reviews",
            payload={"event": event.value, "body": body, "commit_id": commit_id},
        )

    def dismiss_review(self, *, pr_number: int, review_id: int, message: str) -> None:
        self._send(
            method="PUT",
            path=f"repos/{self.repo}/pulls/{pr_number}/reviews/{review_id}/dismissals",
            payload={"message": message, "event": "DISMISS"},
        )

    def request_reviewers(self, *, pr_number: int, users: list[str], teams: list[str]) -> None:
        self._send(
            method="POST",
            path=f"repos/{self.repo}/pulls/{pr_number}/requested_reviewers",
            payload={"reviewers": users, "team_reviewers": teams},
        )

    def merge(self, *, pr_number: int, head_sha: str) -> None:
        self.runner(
            args=["pr", "merge", str(pr_number), "--repo", self.repo, "--squash", "--match-head-commit", head_sha]
        )

    def download_artifact(self, *, run_id: int, name: str, destination: Path) -> Path | None:
        listing = self._get(path=f"repos/{self.repo}/actions/runs/{run_id}/artifacts?name={quote(name, safe='')}")
        if not any(artifact["name"] == name and not artifact["expired"] for artifact in listing["artifacts"]):
            return None
        self.runner(
            args=["run", "download", str(run_id), "--repo", self.repo, "--name", name, "--dir", str(destination)]
        )
        return destination

    def _marker_comment(self, *, pr_number: int, marker: str, author_login: str) -> dict[str, Any] | None:
        for comment in self._paginate(path=f"repos/{self.repo}/issues/{pr_number}/comments"):
            if comment["user"]["login"] == author_login and marker in comment["body"]:
                return comment
        return None

    def _get(self, *, path: str) -> dict[str, Any]:
        return json.loads(self.runner(args=["api", path]))

    def _send(self, *, method: str, path: str, payload: dict[str, object]) -> None:
        self.runner(args=["api", "--method", method, path, "--input", "-"], stdin=json.dumps(payload))

    def _paginate(self, *, path: str, key: str | None = None) -> Iterator[Any]:
        separator = "&" if "?" in path else "?"
        page = 1
        while True:
            response = json.loads(self.runner(args=["api", f"{path}{separator}per_page={PER_PAGE}&page={page}"]))
            items = response if key is None else response[key]
            yield from items
            if len(items) < PER_PAGE:
                return
            page += 1


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes


class HttpTransport(Protocol):
    def __call__(self, *, method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> HttpResponse:
        """Send one request and return the response whatever its status, raising `OSError` when none arrives."""
        ...


def urllib_transport(*, method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> HttpResponse:
    """Send an HTTPS request with the standard library.

    Raises:
        OSError: When the connection fails or times out.
        ValueError: When `url` is not an https URL.

    """
    if not url.startswith("https://"):
        raise ValueError("only https URLs are allowed")
    request = urllib.request.Request(url=url, data=body, headers=dict(headers), method=method)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            return HttpResponse(status=response.status, body=response.read())
    except urllib.error.HTTPError as exc:
        return HttpResponse(status=exc.code, body=exc.read())


@dataclass(frozen=True)
class JiraRest:
    """Jira Cloud port over REST API v3 with basic authentication."""

    base_url: str
    email: str
    token: str = field(repr=False)
    transport: HttpTransport = urllib_transport

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ValueError("the Jira base URL must start with https://")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    def search_open_by_label(self, *, label: str) -> list[JiraIssue]:
        _require_plain_label(label=label)
        return self._search(jql=f'labels = "{label}" AND statusCategory != Done ORDER BY created ASC')

    def search_digest_items(
        self, *, label: str, priorities: Sequence[str], updated_within_days: int
    ) -> list[JiraIssue]:
        _require_plain_label(label=label)
        if not priorities or not all(_JIRA_PRIORITY.fullmatch(priority) for priority in priorities):
            raise ValueError(f"refusing to search for priorities {priorities!r}: expected plain priority names")
        if updated_within_days < 1:
            raise ValueError(f"refusing to search a window of {updated_within_days} days: expected at least 1")
        quoted = ", ".join(f'"{priority}"' for priority in priorities)
        return self._search(
            jql=f'labels = "{label}" AND priority in ({quoted}) AND updated >= -{updated_within_days}d '
            "ORDER BY updated DESC"
        )

    def _search(self, *, jql: str) -> list[JiraIssue]:
        request: dict[str, object] = {"jql": jql, "fields": ["summary", "priority"], "maxResults": JIRA_PAGE_SIZE}
        issues: list[JiraIssue] = []
        while True:
            response = self._send(method="POST", path="/rest/api/3/search/jql", payload=request)
            try:
                issues.extend(self._issue(value=issue) for issue in response["issues"])
                token = response.get("nextPageToken")
                if response.get("isLast", True) or not token:
                    return issues
            except (KeyError, TypeError) as exc:
                raise JiraError(f"unexpected Jira search response: missing {exc}") from exc
            request = {**request, "nextPageToken": token}

    def create_issue(self, *, draft: JiraIssueDraft) -> JiraIssue:
        response = self._send(
            method="POST",
            path="/rest/api/3/issue",
            payload={
                "fields": {
                    "project": {"key": draft.project_key},
                    "issuetype": {"name": draft.issue_type},
                    "summary": draft.summary,
                    "labels": list(draft.labels),
                    "priority": {"name": str(draft.priority)},
                    "description": draft.description,
                }
            },
        )
        try:
            key = str(response["key"])
        except KeyError as exc:
            raise JiraError("unexpected Jira create response: missing 'key'") from exc
        return JiraIssue(key=key, summary=draft.summary, url=self._browse_url(key=key), priority=str(draft.priority))

    def add_comment(self, *, issue_key: str, body: Mapping[str, object]) -> None:
        if not _JIRA_ISSUE_KEY.fullmatch(issue_key):
            raise ValueError(f"refusing to comment on unexpected issue key {issue_key!r}")
        self._send(method="POST", path=f"/rest/api/3/issue/{issue_key}/comment", payload={"body": body})

    def _issue(self, *, value: dict[str, Any]) -> JiraIssue:
        fields = value["fields"]
        priority = fields.get("priority")
        return JiraIssue(
            key=value["key"],
            summary=fields["summary"],
            url=self._browse_url(key=value["key"]),
            priority=None if priority is None else priority["name"],
        )

    def _browse_url(self, *, key: str) -> str:
        return f"{self.base_url}/browse/{key}"

    def _send(self, *, method: str, path: str, payload: Mapping[str, object]) -> dict[str, Any]:
        credentials = base64.b64encode(f"{self.email}:{self.token}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            response = self.transport(
                method=method, url=f"{self.base_url}{path}", headers=headers, body=json.dumps(payload).encode()
            )
        except OSError as exc:
            raise JiraError(f"{method} {path} failed: {exc}") from exc
        if not HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES:
            detail = response.body.decode("utf-8", errors="replace")[:_MAX_ERROR_BODY_CHARS]
            raise JiraError(f"{method} {path} returned HTTP {response.status}: {detail}")
        try:
            decoded = json.loads(response.body) if response.body else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JiraError(f"{method} {path} returned a non-JSON body") from exc
        if not isinstance(decoded, dict):
            raise JiraError(f"{method} {path} returned a non-object body")
        return decoded


@dataclass(frozen=True)
class SlackWebhook:
    """Slack port over an incoming webhook, which posts to the one channel it is bound to."""

    url: str = field(repr=False)
    transport: HttpTransport = urllib_transport

    def __post_init__(self) -> None:
        if not self.url.startswith("https://"):
            raise ValueError("the Slack webhook URL must start with https://")

    def post_message(self, *, text: str) -> None:
        try:
            response = self.transport(
                method="POST",
                url=self.url,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"text": text}).encode(),
            )
        except OSError as exc:
            raise SlackError(f"posting to the Slack webhook failed: {exc}") from exc
        if not HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES:
            detail = response.body.decode("utf-8", errors="replace")[:_MAX_ERROR_BODY_CHARS]
            raise SlackError(f"the Slack webhook returned HTTP {response.status}: {detail}")


def _require_plain_label(*, label: str) -> None:
    if not _JIRA_LABEL.fullmatch(label):
        raise ValueError(f"refusing to search for label {label!r}: only letters, digits, '.', '_' and '-'")


def _timestamp(*, value: str) -> datetime:
    return datetime.fromisoformat(value)


def _conclusion(*, value: str | None) -> RunConclusion | None:
    return None if value is None else RunConclusion(value)
