from infrahub.computed_attribute.queries import ComputedAttributeTransformQuery, TransformNode


class TestComputedAttributeTransformQuery:
    def test_render_query_contains_kind_and_fields(self) -> None:
        q = ComputedAttributeTransformQuery(transform_id="txfm-001")
        rendered = q.render_query()
        assert "CoreTransformPython" in rendered
        assert "id" in rendered
        assert "repository" in rendered
        assert "query" in rendered

    def test_render_query_correct_structure(self) -> None:
        q = ComputedAttributeTransformQuery(transform_id="txfm-001")
        rendered = q.render_query()
        assert "ComputedAttributeFetchTransform" in rendered
        assert "edges" in rendered
        assert "node" in rendered

    def test_parse_response_returns_transform_node(self) -> None:
        q = ComputedAttributeTransformQuery(transform_id="txfm-001")
        response = {
            "CoreTransformPython": {
                "edges": [
                    {
                        "node": {
                            "id": "txfm-001",
                            "file_path": {"value": "transforms/my_transform.py"},
                            "class_name": {"value": "MyTransform"},
                            "timeout": {"value": 60},
                            "convert_query_response": {"value": False},
                            "repository": {
                                "node": {
                                    "id": "repo-001",
                                    "__typename": "CoreRepository",
                                    "name": {"value": "my-repo"},
                                }
                            },
                            "query": {"node": {"id": "query-001"}},
                        }
                    }
                ]
            }
        }
        result = q.parse_response(response=response)
        assert result == TransformNode(
            id="txfm-001",
            file_path="transforms/my_transform.py",
            class_name="MyTransform",
            timeout=60,
            convert_query_response=False,
            repository_id="repo-001",
            repository_typename="CoreRepository",
            repository_name="my-repo",
            query_id="query-001",
        )

    def test_parse_response_returns_none_for_empty_edges(self) -> None:
        q = ComputedAttributeTransformQuery(transform_id="txfm-001")
        result = q.parse_response(response={"CoreTransformPython": {"edges": []}})
        assert result is None

    def test_parse_response_returns_none_for_missing_kind(self) -> None:
        q = ComputedAttributeTransformQuery(transform_id="txfm-001")
        assert q.parse_response(response={}) is None
