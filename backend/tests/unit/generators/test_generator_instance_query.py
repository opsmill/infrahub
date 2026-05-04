from infrahub.generators.models import GeneratorInstanceNode, GeneratorInstanceQuery


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

    def test_parse_response_missing_kind_key(self) -> None:
        q = GeneratorInstanceQuery(definition_id="def-001", object_id="obj-001")
        assert q.parse_response(response={}) == []

    def test_parse_response_skips_nodes_without_id(self) -> None:
        q = GeneratorInstanceQuery(definition_id="def-001", object_id="obj-001")
        response = {
            "CoreGeneratorInstance": {
                "edges": [
                    {"node": {"id": "abc-123", "status": {"value": "pending"}}},
                    {"node": {"status": {"value": "error"}}},
                ]
            }
        }
        result = q.parse_response(response=response)
        assert result == [GeneratorInstanceNode(id="abc-123", status="pending")]
