from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from dependabot_autopilot.adapters import GhCliGitHub, GhCommandError, HttpResponse, JiraRest, SlackWebhook
from dependabot_autopilot.ports import (
    AccountType,
    ChangedFile,
    CheckRun,
    CommitState,
    CommitStatus,
    FileStatus,
    JiraError,
    JiraIssue,
    JiraIssueDraft,
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
    from collections.abc import Mapping, Sequence

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


def test_commit_authors_are_parsed_with_none_for_unlinked_authors() -> None:
    adapter, _ = make_adapter(
        responses={api(f"repos/{REPO}/pulls/10689/commits?{PAGE}"): fixture("pull_commits.handcrafted.json")}
    )

    assert adapter.list_commit_authors(pr_number=10689) == ["dependabot[bot]", None]


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


JIRA_BASE = "https://opsmill.atlassian.net"
JIRA_TOKEN = "s3cret"  # noqa: S105
DBAP = "dbap-0123456789ab"
ADF = {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hi"}]}]}


@dataclass(frozen=True)
class HttpCall:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None

    def json(self) -> object:
        assert self.body is not None
        return json.loads(self.body)


@dataclass
class FakeTransport:
    responses: list[HttpResponse | OSError] = field(default_factory=list)
    calls: list[HttpCall] = field(default_factory=list)

    def __call__(self, *, method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> HttpResponse:
        self.calls.append(HttpCall(method=method, url=url, headers=dict(headers), body=body))
        response = self.responses.pop(0)
        if isinstance(response, OSError):
            raise response
        return response


def jira_ok(name: str, *, status: int = 200) -> HttpResponse:
    return HttpResponse(status=status, body=fixture(name).encode())


def make_jira(*responses: HttpResponse | OSError, base_url: str = JIRA_BASE) -> tuple[JiraRest, FakeTransport]:
    transport = FakeTransport(responses=list(responses))
    return JiraRest(base_url=base_url, email="bot@opsmill.com", token=JIRA_TOKEN, transport=transport), transport


def test_jira_search_posts_the_label_jql_with_basic_auth() -> None:
    jira, transport = make_jira(jira_ok("jira_search_jql_empty.handcrafted.json"))

    assert jira.search_open_by_label(label=DBAP) == []

    (call,) = transport.calls
    assert call.method == "POST"
    assert call.url == f"{JIRA_BASE}/rest/api/3/search/jql"
    assert (
        call.headers["Authorization"] == "Basic " + base64.b64encode(f"bot@opsmill.com:{JIRA_TOKEN}".encode()).decode()
    )
    assert call.headers["Content-Type"] == "application/json"
    assert call.headers["Accept"] == "application/json"
    assert call.json() == {
        "jql": f'labels = "{DBAP}" AND statusCategory != Done ORDER BY created ASC',
        "fields": ["summary", "priority"],
        "maxResults": 50,
    }


def test_jira_search_follows_next_page_tokens() -> None:
    jira, transport = make_jira(
        jira_ok("jira_search_jql_page1.handcrafted.json"), jira_ok("jira_search_jql_page2.handcrafted.json")
    )

    issues = jira.search_open_by_label(label=DBAP)

    assert issues == [
        JiraIssue(
            key="IFC-42",
            summary="[fastapi] Use lifespan state",
            url=f"{JIRA_BASE}/browse/IFC-42",
            priority="Medium",
        ),
        JiraIssue(
            key="IFC-50", summary="[fastapi] Use lifespan state", url=f"{JIRA_BASE}/browse/IFC-50", priority=None
        ),
    ]
    first_request = transport.calls[0].json()
    assert isinstance(first_request, dict)
    assert transport.calls[1].json() == {**first_request, "nextPageToken": "CAEaAggD"}


@pytest.mark.parametrize("label", ['dbap-x" OR project = SECRET OR labels = "y', "tech debt", ""])
def test_jira_search_refuses_labels_that_are_not_plain_tokens(label: str) -> None:
    jira, transport = make_jira()

    with pytest.raises(ValueError, match="label"):
        jira.search_open_by_label(label=label)
    assert transport.calls == []


def test_jira_digest_search_posts_the_label_priority_and_window_jql() -> None:
    jira, transport = make_jira(jira_ok("jira_search_digest.handcrafted.json"))

    issues = jira.search_digest_items(
        label="dependabot-autopilot", priorities=("High", "Medium"), updated_within_days=7
    )

    assert issues == [
        JiraIssue(
            key="IFC-61",
            summary="[jinja2] Sandbox escape fixed upstream",
            url=f"{JIRA_BASE}/browse/IFC-61",
            priority="High",
        ),
        JiraIssue(
            key="IFC-42", summary="[fastapi] Use lifespan state", url=f"{JIRA_BASE}/browse/IFC-42", priority="Medium"
        ),
    ]
    (call,) = transport.calls
    assert call.method == "POST"
    assert call.url == f"{JIRA_BASE}/rest/api/3/search/jql"
    assert call.json() == {
        "jql": 'labels = "dependabot-autopilot" AND priority in ("High", "Medium") AND updated >= -7d '
        "ORDER BY updated DESC",
        "fields": ["summary", "priority"],
        "maxResults": 50,
    }


def test_jira_digest_search_follows_next_page_tokens() -> None:
    jira, transport = make_jira(
        jira_ok("jira_search_jql_page1.handcrafted.json"), jira_ok("jira_search_jql_page2.handcrafted.json")
    )

    issues = jira.search_digest_items(label="dependabot-autopilot", priorities=("Medium",), updated_within_days=7)

    assert [issue.key for issue in issues] == ["IFC-42", "IFC-50"]
    first_request = transport.calls[0].json()
    assert isinstance(first_request, dict)
    assert transport.calls[1].json() == {**first_request, "nextPageToken": "CAEaAggD"}


@pytest.mark.parametrize(
    ("label", "priorities", "days"),
    [
        ('x" OR project = SECRET OR labels = "y', ("High",), 7),
        ("dependabot-autopilot", ('High") OR project = SECRET OR priority in ("Low',), 7),
        ("dependabot-autopilot", ("High\\",), 7),
        ("dependabot-autopilot", (), 7),
        ("dependabot-autopilot", ("High",), 0),
        ("dependabot-autopilot", ("High",), -7),
    ],
)
def test_jira_digest_search_refuses_unsafe_inputs(label: str, priorities: tuple[str, ...], days: int) -> None:
    jira, transport = make_jira()

    with pytest.raises(ValueError, match="refusing"):
        jira.search_digest_items(label=label, priorities=priorities, updated_within_days=days)
    assert transport.calls == []


def test_jira_create_posts_the_draft_without_an_assignee() -> None:
    jira, transport = make_jira(jira_ok("jira_create_issue.handcrafted.json", status=201))
    draft = JiraIssueDraft(
        project_key="IFC",
        issue_type="Task",
        summary="[fastapi] Use lifespan state",
        labels=("tech-debt", "dependabot-autopilot", DBAP),
        priority="Medium",
        description=ADF,
    )

    issue = jira.create_issue(draft=draft)

    assert issue == JiraIssue(
        key="IFC-24", summary="[fastapi] Use lifespan state", url=f"{JIRA_BASE}/browse/IFC-24", priority="Medium"
    )
    (call,) = transport.calls
    assert call.method == "POST"
    assert call.url == f"{JIRA_BASE}/rest/api/3/issue"
    assert call.json() == {
        "fields": {
            "project": {"key": "IFC"},
            "issuetype": {"name": "Task"},
            "summary": "[fastapi] Use lifespan state",
            "labels": ["tech-debt", "dependabot-autopilot", DBAP],
            "priority": {"name": "Medium"},
            "description": ADF,
        }
    }


def test_jira_comment_posts_an_adf_body() -> None:
    jira, transport = make_jira(HttpResponse(status=201, body=b'{"id": "10000"}'))

    jira.add_comment(issue_key="IFC-7", body=ADF)

    (call,) = transport.calls
    assert call.method == "POST"
    assert call.url == f"{JIRA_BASE}/rest/api/3/issue/IFC-7/comment"
    assert call.json() == {"body": ADF}


def test_jira_comment_refuses_an_unexpected_issue_key() -> None:
    jira, transport = make_jira()

    with pytest.raises(ValueError, match="issue key"):
        jira.add_comment(issue_key="../../myself", body=ADF)
    assert transport.calls == []


def test_jira_comment_texts_follow_pages_and_keep_link_urls() -> None:
    jira, transport = make_jira(
        jira_ok("jira_comments_page1.handcrafted.json"), jira_ok("jira_comments_page2.handcrafted.json")
    )

    texts = jira.list_comment_texts(issue_key="IFC-7")

    assert len(texts) == 3
    assert "https://github.com/opsmill/infrahub/pull/10689" in texts[0]
    assert "fastapi 0.115.0 → 0.116.0" in texts[0]
    assert "https://github.com/opsmill/infrahub/pull/10700" in texts[1]
    assert "https://github.com/opsmill/infrahub/pull/10701" in texts[2]
    assert [(call.method, call.url, call.body) for call in transport.calls] == [
        ("GET", f"{JIRA_BASE}/rest/api/3/issue/IFC-7/comment?startAt=0&maxResults=50", None),
        ("GET", f"{JIRA_BASE}/rest/api/3/issue/IFC-7/comment?startAt=2&maxResults=50", None),
    ]


def test_jira_comment_texts_reject_a_malformed_response() -> None:
    jira, _ = make_jira(HttpResponse(status=200, body=b'{"startAt": 0, "total": 1}'))

    with pytest.raises(JiraError, match="comment"):
        jira.list_comment_texts(issue_key="IFC-7")


def test_jira_comment_texts_refuse_an_unexpected_issue_key() -> None:
    jira, transport = make_jira()

    with pytest.raises(ValueError, match="issue key"):
        jira.list_comment_texts(issue_key="../../myself")
    assert transport.calls == []


def test_jira_base_url_trailing_slash_is_ignored() -> None:
    jira, transport = make_jira(jira_ok("jira_search_jql_empty.handcrafted.json"), base_url=f"{JIRA_BASE}/")

    jira.search_open_by_label(label=DBAP)

    assert transport.calls[0].url == f"{JIRA_BASE}/rest/api/3/search/jql"


@pytest.mark.parametrize("jira_url", ["http://opsmill.atlassian.net", "file:///etc/passwd", ""])
def test_jira_base_url_must_be_https(jira_url: str) -> None:
    with pytest.raises(ValueError, match="https"):
        JiraRest(base_url=jira_url, email="bot@opsmill.com", token=JIRA_TOKEN)


def test_jira_http_error_raises_jira_error_with_the_status() -> None:
    jira, _ = make_jira(HttpResponse(status=400, body=b'{"errorMessages": ["The value \'IFC\' does not exist"]}'))

    with pytest.raises(JiraError, match="400"):
        jira.search_open_by_label(label=DBAP)


def test_jira_network_error_raises_jira_error() -> None:
    jira, _ = make_jira(TimeoutError("timed out"))

    with pytest.raises(JiraError, match="timed out"):
        jira.search_open_by_label(label=DBAP)


@pytest.mark.parametrize("body", [b"<html>maintenance</html>", b'{"unexpected": true}'])
def test_jira_malformed_response_raises_jira_error(body: bytes) -> None:
    jira, _ = make_jira(HttpResponse(status=200, body=body))

    with pytest.raises(JiraError):
        jira.search_open_by_label(label=DBAP)


def test_jira_error_does_not_leak_the_token() -> None:
    jira, _ = make_jira(HttpResponse(status=401, body=b"Unauthorized"))

    with pytest.raises(JiraError) as exc_info:
        jira.create_issue(
            draft=JiraIssueDraft(
                project_key="IFC", issue_type="Task", summary="s", labels=(), priority="Low", description=ADF
            )
        )
    assert JIRA_TOKEN not in str(exc_info.value)


WEBHOOK_URL = "https://hooks.slack.com/services/T000/B000/XXXXXXXX"


def make_slack(*responses: HttpResponse | OSError) -> tuple[SlackWebhook, FakeTransport]:
    transport = FakeTransport(responses=list(responses))
    return SlackWebhook(url=WEBHOOK_URL, transport=transport), transport


def test_slack_webhook_posts_the_text_as_json() -> None:
    slack, transport = make_slack(HttpResponse(status=200, body=b"ok"))

    slack.post_message(text="*hello* <https://example.com|there>")

    (call,) = transport.calls
    assert call.method == "POST"
    assert call.url == WEBHOOK_URL
    assert call.headers["Content-Type"] == "application/json"
    assert call.json() == {"text": "*hello* <https://example.com|there>"}


@pytest.mark.parametrize("url", ["http://hooks.slack.com/services/T/B/X", "file:///etc/passwd", ""])
def test_slack_webhook_must_be_https(url: str) -> None:
    with pytest.raises(ValueError, match="https"):
        SlackWebhook(url=url)


def test_slack_webhook_url_is_not_in_its_repr() -> None:
    slack, _ = make_slack()

    assert WEBHOOK_URL not in repr(slack)


def test_slack_http_error_raises_slack_error_without_the_url() -> None:
    slack, _ = make_slack(HttpResponse(status=404, body=b"no_service"))

    with pytest.raises(SlackError, match="404") as exc_info:
        slack.post_message(text="hi")
    assert "no_service" in str(exc_info.value)
    assert WEBHOOK_URL not in str(exc_info.value)


def test_slack_network_error_raises_slack_error() -> None:
    slack, _ = make_slack(TimeoutError("timed out"))

    with pytest.raises(SlackError, match="timed out"):
        slack.post_message(text="hi")
