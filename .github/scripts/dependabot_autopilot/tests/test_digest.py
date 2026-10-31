from __future__ import annotations

import pytest

from dependabot_autopilot.digest import (
    DIGEST_LABEL,
    MAX_DIGEST_ITEMS,
    MAX_TITLE_CHARS,
    post_digest,
    render_digest,
)
from dependabot_autopilot.ports import JiraError, JiraIssue, SlackError
from dependabot_autopilot.tests.fakes import FakeJira, FakeSlack

JIRA = "https://opsmill.atlassian.net"


def issue(key: str, *, priority: str | None = "Medium", summary: str = "[fastapi] Use lifespan state") -> JiraIssue:
    return JiraIssue(key=key, summary=summary, url=f"{JIRA}/browse/{key}", priority=priority)


def item_lines(message: str) -> list[str]:
    return [line for line in message.splitlines() if line.startswith("•")]


def test_no_item_renders_no_message() -> None:
    assert render_digest(items=[]) is None


def test_high_items_are_listed_before_medium_ones_with_their_links() -> None:
    message = render_digest(
        items=[
            issue("IFC-1", priority="Medium", summary="[pydantic] Drop the v1 shim"),
            issue("IFC-2", priority="High", summary="[jinja2] Sandbox escape fixed upstream"),
            issue("IFC-3", priority="Medium", summary="[httpx] Use the new transport API"),
        ]
    )

    assert message is not None
    assert item_lines(message) == [
        f"• *High* <{JIRA}/browse/IFC-2|IFC-2> [jinja2] Sandbox escape fixed upstream",
        f"• *Medium* <{JIRA}/browse/IFC-1|IFC-1> [pydantic] Drop the v1 shim",
        f"• *Medium* <{JIRA}/browse/IFC-3|IFC-3> [httpx] Use the new transport API",
    ]
    assert "3" in message.splitlines()[0]


@pytest.mark.parametrize("priority", ["Low", None])
def test_items_of_other_priorities_are_left_out(priority: str | None) -> None:
    assert render_digest(items=[issue("IFC-1", priority=priority)]) is None


def test_titles_cannot_inject_links_or_special_mentions() -> None:
    message = render_digest(
        items=[issue("IFC-1", summary="<!channel> R&D <https://evil.example|click> <@U123> <!subteam^S1>")]
    )

    assert message is not None
    (line,) = item_lines(message)
    title = line.split("> ", 1)[1]
    assert (
        title == "&lt;!channel&gt; R&amp;D &lt;https://evil.example|click&gt; &lt;@\u200bU123&gt; &lt;!subteam^S1&gt;"
    )


@pytest.mark.parametrize("mention", ["@channel", "@here", "@everyone", "@pol"])
def test_bare_mentions_in_titles_are_neutralized(mention: str) -> None:
    message = render_digest(items=[issue("IFC-1", summary=f"ping {mention} now")])

    assert message is not None
    assert mention not in message


def test_a_multi_line_title_stays_on_its_item_line() -> None:
    message = render_digest(items=[issue("IFC-1", summary="first\n• *High* forged line\r\nthird")])

    assert message is not None
    assert item_lines(message) == [f"• *Medium* <{JIRA}/browse/IFC-1|IFC-1> first • *High* forged line third"]


def test_long_titles_are_truncated() -> None:
    message = render_digest(items=[issue("IFC-1", summary="x" * (MAX_TITLE_CHARS * 3))])

    assert message is not None
    (line,) = item_lines(message)
    title = line.split("> ", 1)[1]
    assert title == "x" * (MAX_TITLE_CHARS - 1) + "…"


def test_truncation_never_splits_an_escaped_character() -> None:
    message = render_digest(items=[issue("IFC-1", summary="&" * (MAX_TITLE_CHARS * 2))])

    assert message is not None
    title = item_lines(message)[0].split("> ", 1)[1]
    assert title == "&amp;" * (MAX_TITLE_CHARS - 1) + "…"


def test_the_item_count_is_capped_with_a_remainder_line() -> None:
    items = [issue(f"IFC-{number}", priority="High") for number in range(1, MAX_DIGEST_ITEMS + 6)]

    message = render_digest(items=items)

    assert message is not None
    lines = item_lines(message)
    assert len(lines) == MAX_DIGEST_ITEMS
    assert lines[0].startswith(f"• *High* <{JIRA}/browse/IFC-1|IFC-1>")
    assert message.splitlines()[-1] == "…and 5 more"


def test_digest_posts_one_message_listing_the_weeks_high_and_medium_items() -> None:
    jira = FakeJira(
        issues={
            "IFC-1": (issue("IFC-1", priority="High"), ("tech-debt", DIGEST_LABEL)),
            "IFC-2": (issue("IFC-2", priority="Medium"), ("tech-debt", DIGEST_LABEL)),
            "IFC-3": (issue("IFC-3", priority="Low"), ("tech-debt", DIGEST_LABEL)),
            "IFC-4": (issue("IFC-4", priority="High"), ("tech-debt", DIGEST_LABEL)),
            "IFC-5": (issue("IFC-5", priority="High"), ("tech-debt",)),
        },
        updated_days_ago={"IFC-4": 8},
    )
    slack = FakeSlack()

    assert post_digest(jira=jira, slack=slack) == 2

    (message,) = slack.messages
    assert [line.split("|")[1].split(">")[0] for line in item_lines(message)] == ["IFC-1", "IFC-2"]


def test_digest_posts_nothing_without_items() -> None:
    jira = FakeJira(issues={"IFC-3": (issue("IFC-3", priority="Low"), (DIGEST_LABEL,))})
    slack = FakeSlack()

    assert post_digest(jira=jira, slack=slack) == 0
    assert slack.messages == []


def test_digest_does_not_post_when_jira_fails() -> None:
    slack = FakeSlack()

    with pytest.raises(JiraError):
        post_digest(jira=FakeJira(fail=True), slack=slack)
    assert slack.messages == []


def test_digest_surfaces_slack_failures() -> None:
    jira = FakeJira(issues={"IFC-1": (issue("IFC-1", priority="High"), (DIGEST_LABEL,))})

    with pytest.raises(SlackError):
        post_digest(jira=jira, slack=FakeSlack(fail=True))
