from typing import Any

from infrahub.core.graphql_query.node_query import NodeID
from infrahub.display_labels.graphql_queries import DisplayLabelNodeIDQuery


class TestDisplayLabelNodeIDQuery:
    def test_render_query_contains_kind_and_id_field(self) -> None:
        q = DisplayLabelNodeIDQuery(kind="CoreTag")
        rendered = q.render_query()
        assert "CoreTag" in rendered
        assert "id" in rendered
        assert "edges" in rendered
        assert "node" in rendered

    def test_render_query_correct_structure(self) -> None:
        q = DisplayLabelNodeIDQuery(kind="InfraDevice")
        rendered = q.render_query()
        assert "InfraDevice" in rendered
        assert "FetchNodeIDs" in rendered
        assert "$offset" in rendered
        assert "$limit" in rendered
        assert "offset: $offset" in rendered
        assert "limit: $limit" in rendered

    def test_parse_response_returns_node_ids(self) -> None:
        q = DisplayLabelNodeIDQuery(kind="CoreTag")
        response = {
            "CoreTag": {
                "edges": [
                    {"node": {"id": "abc-123"}},
                    {"node": {"id": "def-456"}},
                ]
            }
        }
        result = q.parse_response(response=response)
        assert result == [NodeID(id="abc-123"), NodeID(id="def-456")]

    def test_parse_response_empty_edges(self) -> None:
        q = DisplayLabelNodeIDQuery(kind="CoreTag")
        response: dict[str, Any] = {"CoreTag": {"edges": []}}
        assert q.parse_response(response=response) == []

    def test_parse_response_missing_kind_key(self) -> None:
        q = DisplayLabelNodeIDQuery(kind="CoreTag")
        assert q.parse_response(response={}) == []

    def test_parse_response_skips_nodes_without_id(self) -> None:
        q = DisplayLabelNodeIDQuery(kind="CoreTag")
        response = {
            "CoreTag": {
                "edges": [
                    {"node": {"id": "abc-123"}},
                    {"node": {}},
                ]
            }
        }
        result = q.parse_response(response=response)
        assert result == [NodeID(id="abc-123")]
