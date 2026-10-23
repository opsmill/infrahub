from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry.trace import SpanKind

from tests.helpers.trace import recorded_spans

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from opentelemetry.sdk.trace import ReadableSpan

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node

QUERY = """
query {
    TestPerson {
        edges {
            node {
                name {
                    value
                }
            }
        }
    }
}
"""


def _ancestor_span_ids(span: ReadableSpan, spans_by_id: dict[int, ReadableSpan]) -> list[int]:
    ancestors: list[int] = []
    parent = span.parent
    while parent is not None:
        ancestors.append(parent.span_id)
        parent_span = spans_by_id.get(parent.span_id)
        parent = parent_span.parent if parent_span else None
    return ancestors


async def test_database_query_spans_descend_from_the_request_span(
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    create_test_admin: Node,
    car_person_data: dict[str, Node],
) -> None:
    # The block starts the application first, so the spans of its startup queries are not recorded.
    with client:
        with recorded_spans() as exported:
            response = client.post("/graphql", json={"query": QUERY}, headers=admin_headers)
            spans = exported.get_finished_spans()

    assert response.status_code == 200
    edges = response.json()["data"]["TestPerson"]["edges"]
    assert {edge["node"]["name"]["value"] for edge in edges} == {"John", "Jane"}

    (server_span,) = [span for span in spans if span.kind is SpanKind.SERVER]
    query_spans = [span for span in spans if span.name == "execute_db_query_with_metadata"]
    assert query_spans

    spans_by_id = {span.context.span_id: span for span in spans}
    for query_span in query_spans:
        assert query_span.context.trace_id == server_span.context.trace_id
        assert server_span.context.span_id in _ancestor_span_ids(query_span, spans_by_id)
