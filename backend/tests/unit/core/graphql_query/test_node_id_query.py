from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub.core.graphql_query.node_id_query import NodeIDQuery

if TYPE_CHECKING:
    from infrahub_sdk.types import HTTPMethod

KIND = "CoreTag"


class PagedNodeIDRequester:
    """Answer node id queries from a fixed id list by offset and limit, recording each requested limit."""

    def __init__(self, node_ids: list[str]) -> None:
        self.node_ids = node_ids
        self.limits: list[int] = []

    async def __call__(
        self,
        url: str,
        method: HTTPMethod,
        headers: dict[str, Any],
        timeout: int,  # noqa: ASYNC109  the SDK passes the requester its timeout by this name
        payload: dict | None = None,
    ) -> httpx.Response:
        variables = (payload or {})["variables"]
        offset, limit = variables["offset"], variables["limit"]
        self.limits.append(limit)
        edges = [{"node": {"id": node_id}} for node_id in self.node_ids[offset : offset + limit]]
        return httpx.Response(
            status_code=200,
            json={"data": {KIND: {"edges": edges}}},
            request=httpx.Request(method=method.value, url=url),
        )


@dataclass
class FetchAllChunkedTestCase:
    name: str
    pagination_size: int
    chunk_size: int
    node_count: int
    expected_limits: list[int]
    expected_chunk_sizes: list[int]


FETCH_ALL_CHUNKED_TEST_CASES = [
    FetchAllChunkedTestCase(
        name="pagination-size-larger-than-chunk",
        pagination_size=4,
        chunk_size=2,
        node_count=7,
        expected_limits=[4, 4],
        expected_chunk_sizes=[2, 2, 2, 1],
    ),
    FetchAllChunkedTestCase(
        name="pagination-size-smaller-than-chunk",
        pagination_size=1,
        chunk_size=3,
        node_count=7,
        expected_limits=[3, 3, 3],
        expected_chunk_sizes=[3, 3, 1],
    ),
    FetchAllChunkedTestCase(
        name="no-nodes",
        pagination_size=4,
        chunk_size=2,
        node_count=0,
        expected_limits=[4],
        expected_chunk_sizes=[],
    ),
]


@pytest.mark.parametrize("case", FETCH_ALL_CHUNKED_TEST_CASES, ids=[case.name for case in FETCH_ALL_CHUNKED_TEST_CASES])
async def test_fetch_all_chunked_pages_at_pagination_size_and_never_below_chunk(case: FetchAllChunkedTestCase) -> None:
    node_ids = [f"node-{index}" for index in range(case.node_count)]
    requester = PagedNodeIDRequester(node_ids=node_ids)
    client = InfrahubClient(config=Config(pagination_size=case.pagination_size, requester=requester))

    chunks = [
        chunk
        async for chunk in NodeIDQuery(kind=KIND).fetch_all_chunked(
            client=client, branch_name="main", chunk_size=case.chunk_size
        )
    ]

    assert requester.limits == case.expected_limits
    assert [len(chunk) for chunk in chunks] == case.expected_chunk_sizes
    assert [node_id for chunk in chunks for node_id in chunk] == node_ids
