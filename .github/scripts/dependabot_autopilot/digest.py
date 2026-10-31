"""Weekly Slack digest of the High and Medium tech-debt items the autopilot filed or updated."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dependabot_autopilot.opportunities import AUTOPILOT_LABEL, Priority

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dependabot_autopilot.ports import JiraIssue, JiraPort, SlackPort

DIGEST_LABEL = AUTOPILOT_LABEL
DIGEST_PRIORITIES = (Priority.HIGH, Priority.MEDIUM)
DIGEST_WINDOW_DAYS = 7
MAX_DIGEST_ITEMS = 50
MAX_TITLE_CHARS = 150
_ELLIPSIS = "…"
# A zero-width space after "@" keeps Slack from resolving any mention in agent-written text.
_MENTION_BREAK = "@\u200b"


def render_digest(*, items: Sequence[JiraIssue]) -> str | None:
    """Return the Slack mrkdwn message listing High then Medium items, or `None` when there is none to list."""
    ranked = _ranked(items=items)
    if not ranked:
        return None
    lines = [
        f"*Dependabot autopilot: {len(ranked)} High/Medium tech-debt item{'' if len(ranked) == 1 else 's'} "
        f"filed or updated in the last {DIGEST_WINDOW_DAYS} days*"
    ]
    lines.extend(_item_line(item=item) for item in ranked[:MAX_DIGEST_ITEMS])
    if len(ranked) > MAX_DIGEST_ITEMS:
        lines.append(f"{_ELLIPSIS}and {len(ranked) - MAX_DIGEST_ITEMS} more")
    return "\n".join(lines)


def post_digest(*, jira: JiraPort, slack: SlackPort) -> int:
    """Post the week's digest when it lists at least one item, and return how many items it lists.

    Raises:
        JiraError: When the items cannot be read; nothing is posted.
        SlackError: When the message cannot be posted.

    """
    items = jira.search_digest_items(
        label=DIGEST_LABEL, priorities=DIGEST_PRIORITIES, updated_within_days=DIGEST_WINDOW_DAYS
    )
    message = render_digest(items=items)
    if message is None:
        return 0
    slack.post_message(text=message)
    return len(_ranked(items=items))


def _ranked(*, items: Sequence[JiraIssue]) -> list[JiraIssue]:
    ranks = {priority.value: rank for rank, priority in enumerate(DIGEST_PRIORITIES)}
    listed = [(ranks[item.priority], index, item) for index, item in enumerate(items) if item.priority in ranks]
    return [item for _, _, item in sorted(listed)]


def _item_line(*, item: JiraIssue) -> str:
    title = " ".join(item.summary.split())
    if len(title) > MAX_TITLE_CHARS:
        title = title[: MAX_TITLE_CHARS - 1] + _ELLIPSIS
    return f"• *{item.priority}* <{_escape(text=item.url)}|{_escape(text=item.key)}> {_escape(text=title)}"


def _escape(*, text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return escaped.replace("@", _MENTION_BREAK)
