"""Port implementations over external tools and services."""

from __future__ import annotations

import json
import subprocess  # noqa: S404
from dataclasses import dataclass
from datetime import datetime
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
    PullRequest,
    PullRequestState,
    Review,
    ReviewEvent,
    ReviewState,
    RunConclusion,
    RunStatus,
    WorkflowRun,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

PER_PAGE = 100
_RAW_CONTENT = "Accept: application/vnd.github.raw+json"


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

    def upsert_marker_comment(self, *, pr_number: int, marker: str, body: str, author_login: str) -> None:
        if marker not in body:
            raise ValueError("the comment body must contain the marker so the next run can find it")
        for comment in self._paginate(path=f"repos/{self.repo}/issues/{pr_number}/comments"):
            if comment["user"]["login"] == author_login and marker in comment["body"]:
                self._send(
                    method="PATCH", path=f"repos/{self.repo}/issues/comments/{comment['id']}", payload={"body": body}
                )
                return
        self._send(method="POST", path=f"repos/{self.repo}/issues/{pr_number}/comments", payload={"body": body})

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


def _timestamp(*, value: str) -> datetime:
    return datetime.fromisoformat(value)


def _conclusion(*, value: str | None) -> RunConclusion | None:
    return None if value is None else RunConclusion(value)
