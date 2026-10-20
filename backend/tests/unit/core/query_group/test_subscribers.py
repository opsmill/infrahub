"""Which groups the subscriber lookup keeps when the caller asks for one query."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.query_group.subscribers import fetch_subscriber_refs

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient


class _StubClient:
    """Answers the gather query with one group per (query id, subscriber id) pair given."""

    def __init__(self, groups: list[tuple[str | None, str]]) -> None:
        self._groups = groups

    async def execute_graphql(self, **kwargs: Any) -> dict[str, Any]:
        return {
            InfrahubKind.GRAPHQLQUERYGROUP: {
                "edges": [
                    {
                        "node": {
                            "query": {"node": {"id": query_id}} if query_id else {"node": None},
                            "subscribers": {"edges": [{"node": {"id": node_id, "__typename": "TestCar"}}]},
                        }
                    }
                    for query_id, node_id in self._groups
                ]
            }
        }


@pytest.mark.parametrize(
    ("group_query_id", "wanted_query_id", "kept"),
    [
        pytest.param("query01", "query01", True, id="the_same_query_matches"),
        pytest.param("query02", "query01", False, id="another_query_is_dropped"),
        pytest.param(None, "query01", True, id="a_group_with_no_query_is_kept"),
        pytest.param("query02", None, True, id="a_caller_naming_no_query_keeps_every_group"),
    ],
)
async def test_query_ids_drops_only_a_group_of_another_query(
    group_query_id: str | None, wanted_query_id: str | None, kept: bool
) -> None:
    """A group is dropped only when both queries are known and differ."""
    client = _StubClient(groups=[(group_query_id, "n1")])

    refs = await fetch_subscriber_refs(
        client=cast("InfrahubClient", client),
        node_ids=["changed01"],
        branch="main",
        query_ids={wanted_query_id} if wanted_query_id else None,
    )

    assert [ref.id for ref in refs] == (["n1"] if kept else [])


async def test_a_subscriber_is_reported_once_per_matching_group() -> None:
    """Two groups of the wanted query holding the same subscriber report it twice.

    The caller deduplicates, so the lookup must not hide the second report.
    """
    client = _StubClient(groups=[("query01", "n1"), ("query01", "n1"), ("query02", "n1")])

    refs = await fetch_subscriber_refs(
        client=cast("InfrahubClient", client),
        node_ids=["changed01"],
        branch="main",
        query_ids={"query01"},
    )

    assert [(ref.id, ref.query_id) for ref in refs] == [("n1", "query01"), ("n1", "query01")]
