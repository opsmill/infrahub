from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.services.adapters.message_bus import topic_matches


@dataclass
class TopicCase:
    name: str
    topic: str
    routing_key: str
    expected: bool


@pytest.mark.parametrize(
    "case",
    [
        TopicCase(name="hash_matches_everything", topic="#", routing_key="refresh.registry.branches", expected=True),
        TopicCase(name="exact_key", topic="send.echo.request", routing_key="send.echo.request", expected=True),
        TopicCase(name="different_key", topic="send.echo.request", routing_key="send.echo.reply", expected=False),
        TopicCase(
            name="hash_matches_several_words", topic="refresh.#", routing_key="refresh.registry.branches", expected=True
        ),
        TopicCase(
            name="hash_matches_no_word", topic="refresh.#.branches", routing_key="refresh.branches", expected=True
        ),
        TopicCase(
            name="star_matches_one_word",
            topic="refresh.*.branches",
            routing_key="refresh.registry.branches",
            expected=True,
        ),
        TopicCase(
            name="star_does_not_match_two_words",
            topic="refresh.*",
            routing_key="refresh.registry.branches",
            expected=False,
        ),
        TopicCase(name="star_does_not_match_no_word", topic="refresh.*", routing_key="refresh", expected=False),
        TopicCase(name="longer_key", topic="send.echo", routing_key="send.echo.request", expected=False),
        TopicCase(name="other_first_word", topic="git.#", routing_key="refresh.git.fetch", expected=False),
    ],
    ids=lambda case: case.name,
)
def test_topic_matches(case: TopicCase) -> None:
    assert topic_matches(case.topic, case.routing_key) is case.expected
