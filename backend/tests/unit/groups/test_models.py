from __future__ import annotations

import pytest

from infrahub.groups.models import RequestGraphQLQueryGroupUpdate


@pytest.mark.parametrize(
    ("subscribers", "expected"),
    [
        pytest.param([], [], id="no_subscriber"),
        pytest.param(["node-1"], ["node-1"], id="one_subscriber"),
        pytest.param(["node-1", "node-2"], [], id="several_subscribers"),
    ],
)
def test_related_nodes(subscribers: list[str], expected: list[str]) -> None:
    model = RequestGraphQLQueryGroupUpdate(
        branch="main",
        query_name="query01",
        query_id="query-id",
        related_node_ids=[],
        subscribers=subscribers,
        params={},
    )

    assert model.related_nodes == expected
