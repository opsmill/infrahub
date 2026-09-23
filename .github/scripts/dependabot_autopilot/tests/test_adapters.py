from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from dependabot_autopilot.adapters import GhCliGitHub, GhCommandError
from dependabot_autopilot.ports import (
    AccountType,
    ChangedFile,
    CheckRun,
    CommitState,
    CommitStatus,
    FileStatus,
    PullRequest,
    PullRequestState,
    PullRequestSummary,
    Review,
    ReviewEvent,
    ReviewState,
    RunConclusion,
    RunStatus,
    WorkflowRun,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

FIXTURES = Path(__file__).parent / "fixtures"
REPO = "opsmill/infrahub"
HEAD_SHA = "d40beee736f648045309f538af278dc2e34cd3ca"
PAGE = "per_page=100&page=1"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@dataclass(frozen=True)
class Call:
    args: tuple[str, ...]
    stdin: str | None


@dataclass
class FakeRunner:
    responses: dict[tuple[str, ...], str | GhCommandError] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)

    def __call__(self, *, args: Sequence[str], stdin: str | None = None) -> str:
        self.calls.append(Call(args=tuple(args), stdin=stdin))
        response = self.responses.get(tuple(args), "{}")
        if isinstance(response, GhCommandError):
            raise response
        return response

    def payload(self, index: int) -> object:
        stdin = self.calls[index].stdin
        assert stdin is not None
        return json.loads(stdin)


def api(path: str) -> tuple[str, ...]:
    return ("api", path)


def make_adapter(responses: dict[tuple[str, ...], str | GhCommandError]) -> tuple[GhCliGitHub, FakeRunner]:
    runner = FakeRunner(responses=responses)
    return GhCliGitHub(repo=REPO, runner=runner), runner


def test_pull_request_is_parsed() -> None:
    adapter, _ = make_adapter(
        responses={
            api(f"repos/{REPO}/pulls/10689"): fixture("pull.json"),
            api(f"repos/{REPO}/commits/{HEAD_SHA}"): fixture("commit.json"),
        }
    )

    assert adapter.get_pull_request(number=10689) == PullRequest(
        number=10689,
        html_url="https://github.com/opsmill/infrahub/pull/10689",
        author_login="dependabot[bot]",
        base_ref="stable",
        head_sha=HEAD_SHA,
        head_repo_full_name="opsmill/infrahub",
        state=PullRequestState.CLOSED,
        merged=True,
        labels=("dependencies", "python:uv"),
        head_committed_at=datetime(2026, 9, 19, 1, 53, 44, tzinfo=UTC),
    )


def test_reviews_are_parsed() -> None:
    adapter, _ = make_adapter(responses={api(f"repos/{REPO}/pulls/10689/reviews?{PAGE}"): fixture("reviews.json")})

    reviews = adapter.list_reviews(pr_number=10689)

    assert reviews == [
        Review(
            id=reviews[0].id,
            author_login="saltas888",
            author_type=AccountType.USER,
            state=ReviewState.APPROVED,
            commit_id=HEAD_SHA,
            submitted_at=reviews[0].submitted_at,
        ),
        Review(
            id=reviews[1].id,
            author_login="cubic-dev-ai[bot]",
            author_type=AccountType.BOT,
            state=ReviewState.COMMENTED,
            commit_id="2220c06c81ca3c19a30db6aa3ef8bfc0971bf762",
            submitted_at=reviews[1].submitted_at,
        ),
    ]
    assert all(isinstance(review.submitted_at, datetime) for review in reviews)


def test_workflow_runs_are_parsed() -> None:
    adapter, _ = make_adapter(
        responses={api(f"repos/{REPO}/actions/runs?head_sha={HEAD_SHA}&{PAGE}"): fixture("workflow_runs.json")}
    )

    runs = adapter.list_workflow_runs(head_sha=HEAD_SHA)

    assert [(run.name, run.path, run.event, run.status, run.conclusion) for run in runs] == [
        (
            "Claude Code",
            ".github/workflows/claude-code.yml",
            "pull_request_review",
            RunStatus.COMPLETED,
            RunConclusion.SKIPPED,
        ),
        ("CI", ".github/workflows/ci.yml", "pull_request", RunStatus.COMPLETED, RunConclusion.SUCCESS),
        (
            "Publish preview development docker image",
            ".github/workflows/publish-preview-dev-docker-image.yml",
            "pull_request",
            RunStatus.COMPLETED,
            RunConclusion.SKIPPED,
        ),
        (
            "Keyword Scanner",
            ".github/workflows/keyword-scan.yml",
            "pull_request",
            RunStatus.COMPLETED,
            RunConclusion.SKIPPED,
        ),
    ]
    assert {run.head_sha for run in runs} == {HEAD_SHA}


def test_queued_workflow_run_has_no_conclusion() -> None:
    sha = "ab15126fe7e6a5ed5a7d153d82556b9127d25c2b"
    adapter, _ = make_adapter(
        responses={api(f"repos/{REPO}/actions/runs?head_sha={sha}&{PAGE}"): fixture("workflow_runs_queued.json")}
    )

    assert adapter.list_workflow_runs(head_sha=sha) == [
        WorkflowRun(
            id=31125607457,
            name="CI",
            path=".github/workflows/ci.yml",
            event="pull_request",
            head_sha=sha,
            status=RunStatus.QUEUED,
            conclusion=None,
            created_at=datetime(2026, 8, 6, 18, 16, 53, tzinfo=UTC),
        )
    ]


def test_check_runs_carry_app_slug() -> None:
    adapter, _ = make_adapter(
        responses={api(f"repos/{REPO}/commits/{HEAD_SHA}/check-runs?{PAGE}"): fixture("check_runs.json")}
    )

    checks = adapter.list_check_runs(sha=HEAD_SHA)

    assert [(check.name, check.app_slug, check.status, check.conclusion) for check in checks] == [
        ("claude", "github-actions", RunStatus.COMPLETED, RunConclusion.SKIPPED),
        ("coverall-report", "github-actions", RunStatus.COMPLETED, RunConclusion.SUCCESS),
        ("CodSpeed Performance Analysis", "codspeed", RunStatus.COMPLETED, RunConclusion.SUCCESS),
        ("Cloudflare Pages", "cloudflare-workers-and-pages", RunStatus.COMPLETED, RunConclusion.SUCCESS),
    ]


def test_in_progress_check_run_has_no_conclusion() -> None:
    adapter, _ = make_adapter(
        responses={
            api(f"repos/{REPO}/commits/{HEAD_SHA}/check-runs?{PAGE}"): fixture(
                "check_runs_in_progress.handcrafted.json"
            )
        }
    )

    assert adapter.list_check_runs(sha=HEAD_SHA) == [
        CheckRun(
            id=1,
            name="Chromatic",
            app_slug="chromatic-com",
            head_sha=HEAD_SHA,
            status=RunStatus.IN_PROGRESS,
            conclusion=None,
        )
    ]


def test_commit_without_statuses_returns_empty_list() -> None:
    adapter, _ = make_adapter(responses={api(f"repos/{REPO}/commits/{HEAD_SHA}/status?{PAGE}"): fixture("status.json")})

    assert adapter.list_commit_statuses(sha=HEAD_SHA) == []


def test_commit_statuses_are_parsed() -> None:
    adapter, _ = make_adapter(
        responses={api(f"repos/{REPO}/commits/{HEAD_SHA}/status?{PAGE}"): fixture("status_entries.handcrafted.json")}
    )

    assert adapter.list_commit_statuses(sha=HEAD_SHA) == [
        CommitStatus(context="ci/external-lint", state=CommitState.SUCCESS),
        CommitStatus(context="ci/external-scan", state=CommitState.PENDING),
    ]


def test_changed_files_are_parsed() -> None:
    adapter, _ = make_adapter(responses={api(f"repos/{REPO}/pulls/10689/files?{PAGE}"): fixture("pull_files.json")})

    assert adapter.list_changed_files(pr_number=10689) == [
        ChangedFile(path="python_testcontainers/uv.lock", status=FileStatus.MODIFIED, previous_path=None),
        ChangedFile(path="uv.lock", status=FileStatus.MODIFIED, previous_path=None),
    ]


def test_list_endpoints_follow_pagination_until_a_short_page() -> None:
    review = json.loads(fixture("reviews.json"))[0]
    adapter, runner = make_adapter(
        responses={
            api(f"repos/{REPO}/pulls/1/reviews?per_page=100&page=1"): json.dumps([review] * 100),
            api(f"repos/{REPO}/pulls/1/reviews?per_page=100&page=2"): json.dumps([review]),
        }
    )

    assert len(adapter.list_reviews(pr_number=1)) == 101
    assert len(runner.calls) == 2


def test_wrapped_list_endpoints_follow_pagination() -> None:
    page = json.loads(fixture("check_runs.json"))
    check = page["check_runs"][0]
    adapter, runner = make_adapter(
        responses={
            api(f"repos/{REPO}/commits/{HEAD_SHA}/check-runs?per_page=100&page=1"): json.dumps(
                {"total_count": 100, "check_runs": [check] * 100}
            ),
            api(f"repos/{REPO}/commits/{HEAD_SHA}/check-runs?per_page=100&page=2"): json.dumps(
                {"total_count": 100, "check_runs": []}
            ),
        }
    )

    assert len(adapter.list_check_runs(sha=HEAD_SHA)) == 100
    assert len(runner.calls) == 2


def test_read_file_requests_raw_content_at_ref() -> None:
    args = (
        "api",
        "-H",
        "Accept: application/vnd.github.raw+json",
        f"repos/{REPO}/contents/frontend/pnpm-lock.yaml?ref=stable",
    )
    adapter, _ = make_adapter(responses={args: "lockfileVersion: '9.0'\n"})

    assert adapter.read_file(path="frontend/pnpm-lock.yaml", ref="stable") == "lockfileVersion: '9.0'\n"


def test_read_file_returns_none_when_missing() -> None:
    args = ("api", "-H", "Accept: application/vnd.github.raw+json", f"repos/{REPO}/contents/uv.lock?ref={HEAD_SHA}")
    adapter, _ = make_adapter(responses={args: GhCommandError(args=list(args), stderr="gh: Not Found (HTTP 404)")})

    assert adapter.read_file(path="uv.lock", ref=HEAD_SHA) is None


def test_read_file_raises_on_other_errors() -> None:
    args = ("api", "-H", "Accept: application/vnd.github.raw+json", f"repos/{REPO}/contents/uv.lock?ref={HEAD_SHA}")
    adapter, _ = make_adapter(responses={args: GhCommandError(args=list(args), stderr="gh: Server Error (HTTP 502)")})

    with pytest.raises(GhCommandError):
        adapter.read_file(path="uv.lock", ref=HEAD_SHA)


MARKER = "<!-- dependabot-autopilot -->"
APP_LOGIN = "dependabot-autopilot[bot]"


def comments_page(*comments: tuple[int, str, str]) -> str:
    return json.dumps(
        [{"id": comment_id, "user": {"login": login}, "body": body} for comment_id, login, body in comments]
    )


def test_upsert_edits_the_app_comment_holding_the_marker() -> None:
    adapter, runner = make_adapter(
        responses={
            api(f"repos/{REPO}/issues/7/comments?{PAGE}"): comments_page(
                (1, "someone", f"{MARKER} forged"),
                (2, APP_LOGIN, f"{MARKER}\nold"),
            )
        }
    )

    adapter.upsert_marker_comment(pr_number=7, marker=MARKER, body=f"{MARKER}\nnew", author_login=APP_LOGIN)

    assert runner.calls[-1].args == ("api", "--method", "PATCH", f"repos/{REPO}/issues/comments/2", "--input", "-")
    assert runner.payload(-1) == {"body": f"{MARKER}\nnew"}


def test_upsert_creates_a_comment_when_only_forged_markers_exist() -> None:
    adapter, runner = make_adapter(
        responses={api(f"repos/{REPO}/issues/7/comments?{PAGE}"): comments_page((1, "someone", MARKER))}
    )

    adapter.upsert_marker_comment(pr_number=7, marker=MARKER, body=f"{MARKER}\nnew", author_login=APP_LOGIN)

    assert runner.calls[-1].args == ("api", "--method", "POST", f"repos/{REPO}/issues/7/comments", "--input", "-")
    assert runner.payload(-1) == {"body": f"{MARKER}\nnew"}


def test_upsert_rejects_a_body_without_the_marker() -> None:
    adapter, runner = make_adapter(responses={})

    with pytest.raises(ValueError, match="marker"):
        adapter.upsert_marker_comment(pr_number=7, marker=MARKER, body="no marker", author_login=APP_LOGIN)
    assert runner.calls == []


def test_set_labels_replaces_the_label_set() -> None:
    adapter, runner = make_adapter(responses={})

    adapter.set_labels(pr_number=7, labels=["dependencies", "autopilot/safe"])

    assert runner.calls == [
        Call(
            args=("api", "--method", "PUT", f"repos/{REPO}/issues/7/labels", "--input", "-"),
            stdin=json.dumps({"labels": ["dependencies", "autopilot/safe"]}),
        )
    ]


def test_submit_review_pins_the_commit() -> None:
    adapter, runner = make_adapter(responses={})

    adapter.submit_review(pr_number=7, event=ReviewEvent.APPROVE, body="Safe to merge", commit_id=HEAD_SHA)

    assert runner.calls[0].args == ("api", "--method", "POST", f"repos/{REPO}/pulls/7/reviews", "--input", "-")
    assert runner.payload(0) == {"event": "APPROVE", "body": "Safe to merge", "commit_id": HEAD_SHA}


def test_dismiss_review() -> None:
    adapter, runner = make_adapter(responses={})

    adapter.dismiss_review(pr_number=7, review_id=42, message="Head moved")

    assert runner.calls[0].args == (
        "api",
        "--method",
        "PUT",
        f"repos/{REPO}/pulls/7/reviews/42/dismissals",
        "--input",
        "-",
    )
    assert runner.payload(0) == {"message": "Head moved", "event": "DISMISS"}


def test_request_reviewers() -> None:
    adapter, runner = make_adapter(responses={})

    adapter.request_reviewers(pr_number=7, users=[], teams=["backend"])

    assert runner.calls[0].args == (
        "api",
        "--method",
        "POST",
        f"repos/{REPO}/pulls/7/requested_reviewers",
        "--input",
        "-",
    )
    assert runner.payload(0) == {"reviewers": [], "team_reviewers": ["backend"]}


def test_merge_squashes_with_head_commit_match() -> None:
    adapter, runner = make_adapter(responses={})

    adapter.merge(pr_number=7, head_sha=HEAD_SHA)

    assert runner.calls == [
        Call(
            args=("pr", "merge", "7", "--repo", REPO, "--squash", "--match-head-commit", HEAD_SHA),
            stdin=None,
        )
    ]


def test_download_artifact_extracts_into_destination(tmp_path: Path) -> None:
    name = "E2E-testing-pytest-playwright-tutorial"
    adapter, runner = make_adapter(
        responses={api(f"repos/{REPO}/actions/runs/35414053569/artifacts?name={name}"): fixture("run_artifacts.json")}
    )

    assert adapter.download_artifact(run_id=35414053569, name=name, destination=tmp_path) == tmp_path
    assert runner.calls[-1].args == (
        "run",
        "download",
        "35414053569",
        "--repo",
        REPO,
        "--name",
        name,
        "--dir",
        str(tmp_path),
    )


def test_download_artifact_returns_none_without_a_matching_artifact(tmp_path: Path) -> None:
    adapter, runner = make_adapter(
        responses={
            api(f"repos/{REPO}/actions/runs/1/artifacts?name=dependabot-autopilot-verdict"): json.dumps(
                {"total_count": 0, "artifacts": []}
            )
        }
    )

    assert adapter.download_artifact(run_id=1, name="dependabot-autopilot-verdict", destination=tmp_path) is None
    assert len(runner.calls) == 1


def test_download_artifact_skips_expired_artifacts(tmp_path: Path) -> None:
    listing = json.loads(fixture("run_artifacts.json"))
    listing["artifacts"][0]["expired"] = True
    name = listing["artifacts"][0]["name"]
    adapter, runner = make_adapter(
        responses={api(f"repos/{REPO}/actions/runs/35414053569/artifacts?name={name}"): json.dumps(listing)}
    )

    assert adapter.download_artifact(run_id=35414053569, name=name, destination=tmp_path) is None
    assert len(runner.calls) == 1


def test_open_pull_requests_are_listed_for_a_base() -> None:
    adapter, _ = make_adapter(
        responses={api(f"repos/{REPO}/pulls?state=open&base=stable&{PAGE}"): fixture("pulls_open.handcrafted.json")}
    )

    assert adapter.list_open_pull_requests(base="stable") == [
        PullRequestSummary(
            number=10712,
            author_login="dependabot[bot]",
            head_sha="8b1c3f0e2d4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c",
            head_repo_full_name="opsmill/infrahub",
        ),
        PullRequestSummary(
            number=10698,
            author_login="external-contributor",
            head_sha="2f3e4d5c6b7a8f9e0d1c2b3a4f5e6d7c8b9a0f1e",
            head_repo_full_name=None,
        ),
    ]


def test_find_marker_comment_ignores_forged_markers() -> None:
    adapter, _ = make_adapter(
        responses={
            api(f"repos/{REPO}/issues/7/comments?{PAGE}"): comments_page(
                (1, "someone", f"{MARKER} forged"),
                (2, APP_LOGIN, f"{MARKER}\nours"),
            )
        }
    )

    assert adapter.find_marker_comment(pr_number=7, marker=MARKER, author_login=APP_LOGIN) == f"{MARKER}\nours"


def test_find_marker_comment_returns_none_without_an_app_comment() -> None:
    adapter, _ = make_adapter(
        responses={api(f"repos/{REPO}/issues/7/comments?{PAGE}"): comments_page((1, "someone", MARKER))}
    )

    assert adapter.find_marker_comment(pr_number=7, marker=MARKER, author_login=APP_LOGIN) is None
