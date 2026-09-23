from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dependabot_autopilot.adapters import GhCliGitHub, JiraRest, SlackWebhook
from dependabot_autopilot.ports import (
    GitHubError,
    GitHubPort,
    JiraPort,
    PullRequest,
    PullRequestState,
    ReviewEvent,
    ReviewState,
    SlackPort,
)
from dependabot_autopilot.tests.fakes import (
    CommentCreated,
    CommentEdited,
    FakeGitHub,
    FakeJira,
    FakeSlack,
    Merged,
    ReviewDismissed,
)

HEAD_SHA = "d40beee736f648045309f538af278dc2e34cd3ca"
MARKER = "<!-- dependabot-autopilot -->"


def pull_request() -> PullRequest:
    return PullRequest(
        number=7,
        html_url="https://github.com/opsmill/infrahub/pull/7",
        author_login="dependabot[bot]",
        base_ref="stable",
        head_sha=HEAD_SHA,
        head_repo_full_name="opsmill/infrahub",
        state=PullRequestState.OPEN,
        merged=False,
        labels=(),
        head_committed_at=datetime(2026, 9, 19, tzinfo=UTC),
    )


def test_fakes_and_adapters_satisfy_the_ports() -> None:
    github_ports: list[GitHubPort] = [FakeGitHub(), GhCliGitHub(repo="opsmill/infrahub")]
    jira_ports: list[JiraPort] = [
        FakeJira(),
        JiraRest(base_url="https://opsmill.atlassian.net", email="bot@opsmill.com", token="t"),  # noqa: S106
    ]
    slack_ports: list[SlackPort] = [FakeSlack(), SlackWebhook(url="https://hooks.slack.com/services/T/B/X")]

    assert github_ports
    assert jira_ports
    assert slack_ports


def test_marker_comment_is_created_then_edited_in_place() -> None:
    github = FakeGitHub(pull_requests={7: pull_request()})

    github.upsert_marker_comment(pr_number=7, marker=MARKER, body=f"{MARKER} one", author_login=github.acting_login)
    github.upsert_marker_comment(pr_number=7, marker=MARKER, body=f"{MARKER} two", author_login=github.acting_login)

    assert [type(write) for write in github.writes] == [CommentCreated, CommentEdited]
    assert [comment.body for comment in github.comments[7]] == [f"{MARKER} two"]


def test_submitted_review_is_listed_and_dismissable() -> None:
    github = FakeGitHub(pull_requests={7: pull_request()})

    github.submit_review(pr_number=7, event=ReviewEvent.APPROVE, body="ok", commit_id=HEAD_SHA)
    review = github.list_reviews(pr_number=7)[0]
    github.dismiss_review(pr_number=7, review_id=review.id, message="stale")

    assert review.state is ReviewState.APPROVED
    assert review.author_login == github.acting_login
    assert github.list_reviews(pr_number=7)[0].state is ReviewState.DISMISSED
    assert github.writes[-1] == ReviewDismissed(pr_number=7, review_id=review.id, message="stale")


def test_merge_requires_matching_head() -> None:
    github = FakeGitHub(pull_requests={7: pull_request()})

    with pytest.raises(GitHubError):
        github.merge(pr_number=7, head_sha="0" * 40)
    github.merge(pr_number=7, head_sha=HEAD_SHA)

    assert github.writes == [Merged(pr_number=7, head_sha=HEAD_SHA)]
    assert github.get_pull_request(number=7).merged
