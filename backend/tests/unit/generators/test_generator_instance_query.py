import pytest
from pydantic import ValidationError

from infrahub.generators.graphql_queries.queries import GeneratorInstanceQuery
from infrahub.generators.models import GeneratorInstanceNode


class TestGeneratorInstanceQuery:
    def test_render_query_contains_kind_and_fields(self) -> None:
        q = GeneratorInstanceQuery(definition_id="def-001", object_id="obj-001")
        rendered = q.render_query()
        assert "CoreGeneratorInstance" in rendered
        assert "id" in rendered
        assert "status" in rendered

    def test_render_query_correct_structure(self) -> None:
        q = GeneratorInstanceQuery(definition_id="def-001", object_id="obj-001")
        rendered = q.render_query()
        assert "GeneratorInstanceFetch" in rendered
        assert "edges" in rendered
        assert "node" in rendered

    def test_render_query_uses_variable_references(self) -> None:
        q = GeneratorInstanceQuery(definition_id="def-001", object_id="obj-001")
        rendered = q.render_query()
        assert "def-001" not in rendered
        assert "obj-001" not in rendered
        assert "$definition_id" in rendered
        assert "$object_id" in rendered

    def test_get_variables_returns_ids(self) -> None:
        q = GeneratorInstanceQuery(definition_id="def-001", object_id="obj-001")
        assert q.get_variables() == {"definition_id": "def-001", "object_id": "obj-001"}

    def test_parse_response_returns_instance_nodes(self) -> None:
        q = GeneratorInstanceQuery(definition_id="def-001", object_id="obj-001")
        response = {
            "CoreGeneratorInstance": {
                "edges": [
                    {"node": {"id": "abc-123", "status": {"value": "pending"}}},
                    {"node": {"id": "def-456", "status": {"value": "ready"}}},
                ]
            }
        }
        result = q.parse_response(response=response)
        assert result == [
            GeneratorInstanceNode(id="abc-123", status="pending"),
            GeneratorInstanceNode(id="def-456", status="ready"),
        ]

    def test_parse_response_empty_edges(self) -> None:
        q = GeneratorInstanceQuery(definition_id="def-001", object_id="obj-001")
        assert q.parse_response(response={"CoreGeneratorInstance": {"edges": []}}) == []

    def test_parse_response_raises_on_invalid_response(self) -> None:
        q = GeneratorInstanceQuery(definition_id="def-001", object_id="obj-001")
        with pytest.raises(ValidationError):
            q.parse_response(response={})

    def test_parse_response_null_node_is_skipped(self) -> None:
        q = GeneratorInstanceQuery(definition_id="def-001", object_id="obj-001")
        response = {
            "CoreGeneratorInstance": {
                "edges": [
                    {"node": {"id": "abc-123", "status": {"value": "pending"}}},
                    {"node": None},
                ]
            }
        }
        result = q.parse_response(response=response)
        assert result == [GeneratorInstanceNode(id="abc-123", status="pending")]
