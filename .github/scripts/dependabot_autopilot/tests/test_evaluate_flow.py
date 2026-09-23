from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, override

import pytest

from dependabot_autopilot.checks import CiState
from dependabot_autopilot.decision import Action
from dependabot_autopilot.flow import (
    ANALYSIS_WORKFLOW,
    ANALYSIS_WORKFLOW_PATH,
    MARKER,
    VERDICT_ARTIFACT,
    Config,
    SuppliedReport,
    escalate,
    evaluate,
    invalidate,
    sweep,
)
from dependabot_autopilot.ports import (
    AccountType,
    ChangedFile,
    CheckRun,
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
from dependabot_autopilot.tests.fakes import (
    CommentCreated,
    CommentEdited,
    FakeGitHub,
    LabelsSet,
    Merged,
    ReviewDismissed,
    ReviewersRequested,
    ReviewSubmitted,
)

if TYPE_CHECKING:
    from pathlib import Path

REPO = "opsmill/infrahub"
APP_LOGIN = "opsmill-dependabot-autopilot[bot]"
PR_NUMBER = 10689
HEAD_SHA = "d40beee736f648045309f538af278dc2e34cd3ca"
NEW_HEAD_SHA = "e51cfff847f759156410f649bf389ed3f45de4db"
OLD_SHA = "0123456789abcdef0123456789abcdef01234567"
PUSHED_AT = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)
NOW = PUSHED_AT + timedelta(minutes=20)
RUN_URL = "https://github.com/opsmill/infrahub/actions/runs/1"
UV_LOCK = '[[package]]\nname = "fastapi"\nversion = "{version}"\n'


def config(*, merge_enabled: bool = False, fallback_reviewer: str = "devops") -> Config:
    return Config(repo=REPO, app_login=APP_LOGIN, merge_enabled=merge_enabled, fallback_reviewer=fallback_reviewer)


def pull_request(**changes: object) -> PullRequest:
    base = PullRequest(
        number=PR_NUMBER,
        html_url=f"https://github.com/{REPO}/pull/{PR_NUMBER}",
        author_login="dependabot[bot]",
        base_ref="stable",
        head_sha=HEAD_SHA,
        head_repo_full_name=REPO,
        state=PullRequestState.OPEN,
        merged=False,
        labels=("dependencies",),
        head_committed_at=PUSHED_AT,
    )
    return dataclasses.replace(base, **changes)


WORKFLOW_PATHS = {ANALYSIS_WORKFLOW: ANALYSIS_WORKFLOW_PATH, "CI": ".github/workflows/ci.yml"}


def workflow_run(
    *, run_id: int, name: str, head_sha: str = HEAD_SHA, status: RunStatus = RunStatus.COMPLETED
) -> WorkflowRun:
    return WorkflowRun(
        id=run_id,
        name=name,
        path=WORKFLOW_PATHS.get(name, f".github/workflows/{name}.yml"),
        event="pull_request",
        head_sha=head_sha,
        status=status,
        conclusion=RunConclusion.SUCCESS if status is RunStatus.COMPLETED else None,
        created_at=PUSHED_AT + timedelta(seconds=run_id),
    )


def impact(
    *, summary: str = "`Request.state` is read-only", path: str = "backend/app.py", line: int = 12
) -> dict[str, object]:
    return {"summary": summary, "path": path, "line": line}


def report_document(
    *,
    verdict: str = "safe-to-merge",
    head_sha: str = HEAD_SHA,
    impacts: list[dict[str, object]] | None = None,
    report_markdown: str = "## fastapi 0.131.0 → 0.132.0\n\nNo usage affected.",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "pr_number": PR_NUMBER,
        "head_sha": head_sha,
        "verdict": verdict,
        "packages": [
            {
                "name": "fastapi",
                "ecosystem": "uv",
                "from_version": "0.131.0",
                "to_version": "0.132.0",
                "verdict": verdict,
                "impacts": impacts if impacts is not None else ([impact()] if verdict == "needs-code-changes" else []),
                "opportunities": [],
            }
        ],
        "report_markdown": report_markdown,
    }


def write_report(*, directory: Path, document: dict[str, object]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "verdict.json").write_text(json.dumps(document), encoding="utf-8")
    return directory


def repository(
    *,
    tmp_path: Path,
    document: dict[str, object] | None = None,
    pr: PullRequest | None = None,
    ci_status: RunStatus = RunStatus.COMPLETED,
    changed: tuple[str, ...] = (".github/workflows/ci.yml",),
) -> FakeGitHub:
    github = FakeGitHub(acting_login=APP_LOGIN)
    github.pull_requests[PR_NUMBER] = pr or pull_request()
    github.workflow_runs = [
        workflow_run(run_id=42, name=ANALYSIS_WORKFLOW),
        workflow_run(run_id=43, name="CI", status=ci_status),
    ]
    github.changed_files[PR_NUMBER] = [
        ChangedFile(path=path, status=FileStatus.MODIFIED, previous_path=None) for path in changed
    ]
    github.files[".github/CODEOWNERS", "stable"] = "uv.lock @opsmill/backend\n"
    if document is not None:
        github.artifacts[42, VERDICT_ARTIFACT] = write_report(directory=tmp_path / "artifact-42", document=document)
    return github


def push_new_head(*, github: FakeGitHub, tmp_path: Path, document: dict[str, object]) -> None:
    github.pull_requests[PR_NUMBER] = dataclasses.replace(
        github.pull_requests[PR_NUMBER], head_sha=NEW_HEAD_SHA, head_committed_at=PUSHED_AT + timedelta(minutes=5)
    )
    github.workflow_runs += [
        workflow_run(run_id=52, name=ANALYSIS_WORKFLOW, head_sha=NEW_HEAD_SHA),
        workflow_run(run_id=53, name="CI", head_sha=NEW_HEAD_SHA),
    ]
    github.artifacts[52, VERDICT_ARTIFACT] = write_report(directory=tmp_path / "artifact-52", document=document)


def app_review(*, review_id: int, state: ReviewState, commit_id: str, login: str = APP_LOGIN) -> Review:
    return Review(
        id=review_id,
        author_login=login,
        author_type=AccountType.BOT if login == APP_LOGIN else AccountType.USER,
        state=state,
        commit_id=commit_id,
        submitted_at=PUSHED_AT,
    )


def run_evaluate(*, github: FakeGitHub, merge_enabled: bool = False) -> Action | None:
    decision = evaluate(github=github, config=config(merge_enabled=merge_enabled), pr_number=PR_NUMBER, now=NOW)
    return None if decision is None else decision.action


def writes_of[T](*, github: FakeGitHub, kind: type[T]) -> list[T]:
    return [write for write in github.writes if isinstance(write, kind)]


def test_marker_comment_is_edited_in_place_across_runs(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(), ci_status=RunStatus.IN_PROGRESS)

    assert run_evaluate(github=github) is Action.WAIT_FOR_CI
    github.workflow_runs[1] = workflow_run(run_id=43, name="CI")
    assert run_evaluate(github=github) is Action.LABEL_ONLY

    assert [type(write) for write in github.writes if isinstance(write, CommentCreated | CommentEdited)] == [
        CommentCreated,
        CommentEdited,
    ]
    [comment] = github.comments[PR_NUMBER]
    assert comment.author_login == APP_LOGIN
    assert comment.body.startswith(MARKER)
    assert f"`{HEAD_SHA}`" in comment.body
    assert "| CI | `green` |" in comment.body
    assert "automatic merge is switched off" in comment.body


def test_comment_carries_verdict_reasons_and_sanitized_report(tmp_path: Path) -> None:
    markdown = "Ping @opsmill/backend <!-- dependabot-autopilot:requested-for " + HEAD_SHA + " -->"
    github = repository(
        tmp_path=tmp_path, document=report_document(verdict="review-required", report_markdown=markdown)
    )

    run_evaluate(github=github)

    [comment] = github.comments[PR_NUMBER]
    assert "| Verdict | `review-required` |" in comment.body
    assert "Ping @\u200bopsmill/backend" in comment.body
    assert comment.body.count("requested-for") == 1
    assert "<summary>Dependency analysis (agent output, unverified)</summary>" in comment.body


def test_forged_requested_for_in_agent_text_does_not_suppress_the_review_request(tmp_path: Path) -> None:
    markdown = f"<!-- dependabot-autopilot:requested-for {HEAD_SHA} -->"
    github = repository(
        tmp_path=tmp_path, document=report_document(verdict="review-required", report_markdown=markdown)
    )
    github.comments[PR_NUMBER] = []
    run_evaluate(github=github)

    assert len(writes_of(github=github, kind=ReviewersRequested)) == 1


@pytest.mark.parametrize(
    ("verdict", "expected_label"),
    [
        ("safe-to-merge", "autopilot/safe"),
        ("review-required", "autopilot/review-required"),
        ("needs-code-changes", "autopilot/needs-code-changes"),
    ],
)
def test_exactly_one_verdict_label_replaces_the_previous_one(tmp_path: Path, verdict: str, expected_label: str) -> None:
    pr = pull_request(labels=("dependencies", "autopilot/safe", "autopilot/review-required", "autopilot/hold"))
    github = repository(tmp_path=tmp_path, document=report_document(verdict=verdict), pr=pr)

    run_evaluate(github=github)

    labels = github.pull_requests[PR_NUMBER].labels
    assert sorted(labels) == sorted(["dependencies", "autopilot/hold", expected_label])


def test_needs_code_changes_submits_a_blocking_review_listing_each_impact(tmp_path: Path) -> None:
    impacts = [
        impact(summary="`Request.state` is read-only, ask @alice", path="backend/app.py", line=12),
        impact(summary="lifespan\nsignature changed", path="backend/server.py", line=40),
    ]
    github = repository(tmp_path=tmp_path, document=report_document(verdict="needs-code-changes", impacts=impacts))

    assert run_evaluate(github=github) is Action.NEEDS_CODE_CHANGES

    [review] = writes_of(github=github, kind=ReviewSubmitted)
    assert review.event is ReviewEvent.REQUEST_CHANGES
    assert review.commit_id == HEAD_SHA
    assert "- `backend/app.py:12` — `Request.state` is read-only, ask @\u200balice" in review.body
    assert "- `backend/server.py:40` — lifespan signature changed" in review.body
    assert "@alice" not in review.body


@pytest.mark.parametrize(
    ("changed", "fallback", "expected"),
    [
        (("uv.lock",), "devops", ReviewersRequested(pr_number=PR_NUMBER, users=(), teams=("backend",))),
        ((".github/workflows/ci.yml",), "devops", ReviewersRequested(pr_number=PR_NUMBER, users=(), teams=("devops",))),
        (
            (".github/workflows/ci.yml",),
            "@opsmill/release",
            ReviewersRequested(pr_number=PR_NUMBER, users=(), teams=("release",)),
        ),
    ],
)
def test_reviewers_are_requested_from_owners_or_the_fallback(
    tmp_path: Path, changed: tuple[str, ...], fallback: str, expected: ReviewersRequested
) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(verdict="review-required"), changed=changed)
    github.files["uv.lock", "stable"] = UV_LOCK.format(version="0.131.0")
    github.files["uv.lock", HEAD_SHA] = UV_LOCK.format(version="0.132.0")

    evaluate(github=github, config=config(fallback_reviewer=fallback), pr_number=PR_NUMBER, now=NOW)

    assert writes_of(github=github, kind=ReviewersRequested) == [expected]


def test_no_reviewer_request_without_owner_or_fallback(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(verdict="review-required"))

    evaluate(github=github, config=config(fallback_reviewer=""), pr_number=PR_NUMBER, now=NOW)

    assert writes_of(github=github, kind=ReviewersRequested) == []


def test_reviewers_are_requested_once_per_head_sha(tmp_path: Path) -> None:
    document = report_document(verdict="review-required")
    github = repository(tmp_path=tmp_path, document=document)

    run_evaluate(github=github)
    run_evaluate(github=github)
    assert len(writes_of(github=github, kind=ReviewersRequested)) == 1

    push_new_head(
        github=github, tmp_path=tmp_path, document=report_document(verdict="review-required", head_sha=NEW_HEAD_SHA)
    )
    run_evaluate(github=github)
    run_evaluate(github=github)
    assert len(writes_of(github=github, kind=ReviewersRequested)) == 2


def test_safe_verdict_with_green_ci_approves_then_merges_the_analysed_sha(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, document=report_document())

    assert run_evaluate(github=github, merge_enabled=True) is Action.APPROVE_AND_MERGE

    approve_index, review = next(
        (index, write) for index, write in enumerate(github.writes) if isinstance(write, ReviewSubmitted)
    )
    merge_index, merged = next((index, write) for index, write in enumerate(github.writes) if isinstance(write, Merged))
    assert review.event is ReviewEvent.APPROVE
    assert review.commit_id == HEAD_SHA
    assert approve_index < merge_index
    assert merged == Merged(pr_number=PR_NUMBER, head_sha=HEAD_SHA)


def test_refused_merge_is_reported_on_the_comment(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, document=report_document())
    github.fail_merge = True

    assert run_evaluate(github=github, merge_enabled=True) is Action.APPROVE_AND_MERGE

    [comment] = github.comments[PR_NUMBER]
    assert "**Merge attempt failed**" in comment.body
    assert writes_of(github=github, kind=Merged) == []


@pytest.mark.parametrize(
    ("verdict", "merge_enabled"),
    [
        ("safe-to-merge", False),
        ("safe-to-merge", True),
        ("review-required", False),
        ("needs-code-changes", False),
    ],
)
def test_second_evaluate_on_the_same_head_writes_nothing(tmp_path: Path, verdict: str, merge_enabled: bool) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(verdict=verdict))
    run_evaluate(github=github, merge_enabled=merge_enabled)
    writes_after_first_run = list(github.writes)

    run_evaluate(github=github, merge_enabled=merge_enabled)

    assert writes_after_first_run
    assert github.writes == writes_after_first_run


def test_pending_analysis_clears_the_previous_verdict_label(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, pr=pull_request(labels=("dependencies", "autopilot/safe")))
    github.workflow_runs[0] = workflow_run(run_id=42, name=ANALYSIS_WORKFLOW, status=RunStatus.IN_PROGRESS)

    assert run_evaluate(github=github) is Action.PENDING

    assert github.pull_requests[PR_NUMBER].labels == ("dependencies",)
    assert writes_of(github=github, kind=ReviewersRequested) == []


def test_new_lockfile_package_escalates_and_names_the_package(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(), changed=("uv.lock",))
    github.files["uv.lock", "stable"] = UV_LOCK.format(version="0.131.0")
    github.files["uv.lock", HEAD_SHA] = UV_LOCK.format(version="0.132.0") + '[[package]]\nname = "annotated-doc"\n'

    assert run_evaluate(github=github, merge_enabled=True) is Action.REVIEW_REQUIRED

    [comment] = github.comments[PR_NUMBER]
    assert "`annotated-doc`" in comment.body
    assert writes_of(github=github, kind=Merged) == []


def test_commit_by_another_author_escalates_with_a_reason(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, document=report_document())
    github.commit_authors[PR_NUMBER] = ["dependabot[bot]", "alice"]

    assert run_evaluate(github=github, merge_enabled=True) is Action.REVIEW_REQUIRED

    [comment] = github.comments[PR_NUMBER]
    assert "pull request contains commits not authored by dependabot[bot]" in comment.body
    assert writes_of(github=github, kind=Merged) == []


def test_unparseable_lockfile_escalates_with_a_reason(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(), changed=("uv.lock",))
    github.files["uv.lock", "stable"] = UV_LOCK.format(version="0.131.0")
    github.files["uv.lock", HEAD_SHA] = "not = [valid"

    assert run_evaluate(github=github, merge_enabled=True) is Action.REVIEW_REQUIRED

    [comment] = github.comments[PR_NUMBER]
    assert "new packages could not be checked" in comment.body


def test_supplied_report_claiming_another_head_than_its_run_is_malformed(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, pr=pull_request(head_sha=OLD_SHA))
    github.workflow_runs = [workflow_run(run_id=43, name="CI", head_sha=OLD_SHA)]
    forged = SuppliedReport(
        directory=write_report(directory=tmp_path / "forged", document=report_document(head_sha=HEAD_SHA)),
        run_head_sha=OLD_SHA,
    )

    decision = evaluate(github=github, config=config(merge_enabled=True), pr_number=PR_NUMBER, now=NOW, supplied=forged)

    assert decision is not None
    assert decision.action is Action.REVIEW_REQUIRED
    assert any("the analysis run was for" in reason for reason in decision.reasons)


def test_supplied_report_is_used_for_its_head(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path)
    supplied = SuppliedReport(
        directory=write_report(directory=tmp_path / "supplied", document=report_document()), run_head_sha=HEAD_SHA
    )

    decision = evaluate(
        github=github, config=config(merge_enabled=True), pr_number=PR_NUMBER, now=NOW, supplied=supplied
    )

    assert decision is not None
    assert decision.action is Action.APPROVE_AND_MERGE
    assert decision.ci_state is CiState.GREEN


def test_completed_analysis_without_artifact_is_review_required(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path)

    assert run_evaluate(github=github, merge_enabled=True) is Action.REVIEW_REQUIRED


@pytest.mark.parametrize(
    ("path", "event"),
    [(".github/workflows/impostor.yml", "pull_request"), (ANALYSIS_WORKFLOW_PATH, "workflow_dispatch")],
    ids=["other-path", "other-event"],
)
def test_analysis_run_lookup_ignores_runs_of_another_workflow_or_event(tmp_path: Path, path: str, event: str) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(verdict="review-required"))
    github.workflow_runs.append(
        dataclasses.replace(workflow_run(run_id=99, name=ANALYSIS_WORKFLOW), path=path, event=event)
    )
    github.artifacts[99, VERDICT_ARTIFACT] = write_report(
        directory=tmp_path / "artifact-99", document=report_document()
    )

    assert run_evaluate(github=github, merge_enabled=True) is Action.REVIEW_REQUIRED
    assert writes_of(github=github, kind=Merged) == []


def test_invalidate_dismisses_only_app_approvals_of_other_commits(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path)
    github.reviews[PR_NUMBER] = [
        app_review(review_id=1, state=ReviewState.APPROVED, commit_id=OLD_SHA),
        app_review(review_id=2, state=ReviewState.APPROVED, commit_id=HEAD_SHA),
        app_review(review_id=3, state=ReviewState.CHANGES_REQUESTED, commit_id=OLD_SHA),
        app_review(review_id=4, state=ReviewState.APPROVED, commit_id=OLD_SHA, login="alice"),
    ]

    invalidate(github=github, config=config(), pr_number=PR_NUMBER)

    assert [write.review_id for write in writes_of(github=github, kind=ReviewDismissed)] == [1]
    assert len(github.writes) == 1


@pytest.mark.parametrize(
    "pr",
    [
        pull_request(author_login="alice"),
        pull_request(base_ref="develop"),
        pull_request(head_repo_full_name="someone/infrahub"),
        pull_request(state=PullRequestState.CLOSED, merged=True),
    ],
    ids=["other-author", "other-base", "fork", "merged"],
)
def test_out_of_scope_pull_request_gets_no_writes(tmp_path: Path, pr: PullRequest) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(verdict="review-required"), pr=pr)
    github.reviews[PR_NUMBER] = [app_review(review_id=1, state=ReviewState.APPROVED, commit_id=OLD_SHA)]

    assert run_evaluate(github=github, merge_enabled=True) is None
    invalidate(github=github, config=config(), pr_number=PR_NUMBER)
    escalate(github=github, config=config(), pr_number=PR_NUMBER, run_url=RUN_URL)

    assert github.writes == []


def test_sweep_evaluates_only_open_dependabot_pull_requests(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(verdict="review-required"))
    github.pull_requests[7] = pull_request(number=7, author_login="alice", head_sha=OLD_SHA)

    assert sweep(github=github, config=config(), now=NOW, run_url=RUN_URL) is True

    assert {write.pr_number for write in github.writes if isinstance(write, LabelsSet)} == {PR_NUMBER}


class ChecksUnavailableGitHub(FakeGitHub):
    @override
    def list_check_runs(self, *, sha: str) -> list[CheckRun]:
        raise RuntimeError(f"check runs of {sha} unavailable")


def test_sweep_escalates_a_pull_request_whose_evaluation_fails() -> None:
    github = ChecksUnavailableGitHub(acting_login=APP_LOGIN)
    github.pull_requests[PR_NUMBER] = pull_request()

    assert sweep(github=github, config=config(), now=NOW, run_url=RUN_URL) is False

    assert github.pull_requests[PR_NUMBER].labels == ("dependencies", "autopilot/review-required")
    [comment] = github.comments[PR_NUMBER]
    assert RUN_URL in comment.body


def test_escalate_keeps_the_requested_for_record(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(verdict="review-required"))
    run_evaluate(github=github)

    escalate(github=github, config=config(), pr_number=PR_NUMBER, run_url=RUN_URL)
    run_evaluate(github=github)

    assert len(writes_of(github=github, kind=ReviewersRequested)) == 1


def test_escalate_dismisses_every_app_approval_including_the_head(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path)
    github.reviews[PR_NUMBER] = [
        app_review(review_id=1, state=ReviewState.APPROVED, commit_id=OLD_SHA),
        app_review(review_id=2, state=ReviewState.APPROVED, commit_id=HEAD_SHA),
        app_review(review_id=3, state=ReviewState.APPROVED, commit_id=HEAD_SHA, login="alice"),
    ]

    escalate(github=github, config=config(), pr_number=PR_NUMBER, run_url=RUN_URL)

    assert [write.review_id for write in writes_of(github=github, kind=ReviewDismissed)] == [1, 2]
    assert "autopilot/review-required" in github.pull_requests[PR_NUMBER].labels


class DismissalRefusedGitHub(FakeGitHub):
    @override
    def dismiss_review(self, *, pr_number: int, review_id: int, message: str) -> None:
        if review_id == 1:
            raise GitHubError(f"dismissal of review {review_id} refused")
        super().dismiss_review(pr_number=pr_number, review_id=review_id, message=message)


def test_escalate_still_labels_when_a_dismissal_fails() -> None:
    github = DismissalRefusedGitHub(acting_login=APP_LOGIN)
    github.pull_requests[PR_NUMBER] = pull_request()
    github.reviews[PR_NUMBER] = [
        app_review(review_id=1, state=ReviewState.APPROVED, commit_id=OLD_SHA),
        app_review(review_id=2, state=ReviewState.APPROVED, commit_id=HEAD_SHA),
    ]

    escalate(github=github, config=config(), pr_number=PR_NUMBER, run_url=RUN_URL)

    assert [write.review_id for write in writes_of(github=github, kind=ReviewDismissed)] == [2]
    assert github.pull_requests[PR_NUMBER].labels == ("dependencies", "autopilot/review-required")


class EscalationFailsForOnePullRequestGitHub(ChecksUnavailableGitHub):
    @override
    def set_labels(self, *, pr_number: int, labels: list[str]) -> None:
        if pr_number == PR_NUMBER:
            raise GitHubError(f"labels of #{pr_number} cannot be set")
        super().set_labels(pr_number=pr_number, labels=labels)


def test_sweep_continues_after_an_escalation_fails() -> None:
    github = EscalationFailsForOnePullRequestGitHub(acting_login=APP_LOGIN)
    github.pull_requests[PR_NUMBER] = pull_request()
    github.pull_requests[7] = pull_request(number=7, head_sha=OLD_SHA)

    assert sweep(github=github, config=config(), now=NOW, run_url=RUN_URL) is False

    assert github.pull_requests[7].labels == ("dependencies", "autopilot/review-required")


def approvals(*, github: FakeGitHub) -> list[ReviewSubmitted]:
    return [write for write in writes_of(github=github, kind=ReviewSubmitted) if write.event is ReviewEvent.APPROVE]


@pytest.mark.parametrize(
    ("merge_enabled", "labels", "reviews"),
    [
        (False, ("dependencies",), []),
        (True, ("dependencies", "autopilot/hold"), []),
        (
            True,
            ("dependencies",),
            [app_review(review_id=1, state=ReviewState.CHANGES_REQUESTED, commit_id=HEAD_SHA, login="alice")],
        ),
    ],
    ids=["merge-switched-off", "hold-label", "human-change-request"],
)
def test_safe_verdict_held_back_is_neither_approved_nor_merged(
    tmp_path: Path, merge_enabled: bool, labels: tuple[str, ...], reviews: list[Review]
) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(), pr=pull_request(labels=labels))
    github.reviews[PR_NUMBER] = reviews

    assert run_evaluate(github=github, merge_enabled=merge_enabled) is Action.LABEL_ONLY

    assert approvals(github=github) == []
    assert writes_of(github=github, kind=Merged) == []


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [("review-required", Action.REVIEW_REQUIRED), ("needs-code-changes", Action.NEEDS_CODE_CHANGES)],
)
def test_escalating_verdict_dismisses_the_app_approval_of_the_head(
    tmp_path: Path, verdict: str, expected: Action
) -> None:
    github = repository(tmp_path=tmp_path, document=report_document(verdict=verdict))
    github.reviews[PR_NUMBER] = [app_review(review_id=1, state=ReviewState.APPROVED, commit_id=HEAD_SHA)]

    assert run_evaluate(github=github, merge_enabled=True) is expected

    assert [write.review_id for write in writes_of(github=github, kind=ReviewDismissed)] == [1]
    assert writes_of(github=github, kind=Merged) == []


@dataclass
class HeadMovesAfterApprovalGitHub(FakeGitHub):
    @override
    def submit_review(self, *, pr_number: int, event: ReviewEvent, body: str, commit_id: str) -> None:
        super().submit_review(pr_number=pr_number, event=event, body=body, commit_id=commit_id)
        self.pull_requests[pr_number] = dataclasses.replace(self.pull_requests[pr_number], head_sha=NEW_HEAD_SHA)


def test_head_moving_between_approval_and_merge_refuses_the_merge(tmp_path: Path) -> None:
    template = repository(tmp_path=tmp_path, document=report_document())
    github = HeadMovesAfterApprovalGitHub(
        **{field.name: getattr(template, field.name) for field in dataclasses.fields(template)}
    )

    assert run_evaluate(github=github, merge_enabled=True) is Action.APPROVE_AND_MERGE

    assert github.merge_attempts == [HEAD_SHA]
    assert writes_of(github=github, kind=Merged) == []
    [comment] = github.comments[PR_NUMBER]
    assert "**Merge attempt failed**" in comment.body


def test_merge_retried_after_a_failure_approves_and_merges_once(tmp_path: Path) -> None:
    github = repository(tmp_path=tmp_path, document=report_document())
    github.fail_merge = True
    run_evaluate(github=github, merge_enabled=True)

    github.fail_merge = False
    assert run_evaluate(github=github, merge_enabled=True) is Action.APPROVE_AND_MERGE

    assert len(approvals(github=github)) == 1
    assert writes_of(github=github, kind=Merged) == [Merged(pr_number=PR_NUMBER, head_sha=HEAD_SHA)]


@pytest.mark.parametrize("new_head_status", [RunStatus.COMPLETED, RunStatus.IN_PROGRESS], ids=["analysed", "pending"])
def test_evaluate_on_a_new_head_dismisses_the_approval_of_the_old_head(
    tmp_path: Path, new_head_status: RunStatus
) -> None:
    github = repository(tmp_path=tmp_path, document=report_document())
    github.fail_merge = True
    run_evaluate(github=github, merge_enabled=True)
    [old_approval] = [review for review in github.reviews[PR_NUMBER] if review.state is ReviewState.APPROVED]

    push_new_head(github=github, tmp_path=tmp_path, document=report_document(head_sha=NEW_HEAD_SHA))
    github.workflow_runs[-2] = workflow_run(
        run_id=52, name=ANALYSIS_WORKFLOW, head_sha=NEW_HEAD_SHA, status=new_head_status
    )
    run_evaluate(github=github, merge_enabled=True)

    assert [write.review_id for write in writes_of(github=github, kind=ReviewDismissed)] == [old_approval.id]
