import pytest

from infrahub.computed_attribute.graphql_queries.queries import ComputedAttributeTransformQuery, TransformNode


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

    def test_render_query_uses_variable_reference_not_literal_for_uuid(self) -> None:
        transform_id = "12345678-1234-5678-1234-567812345678"
        q = ComputedAttributeTransformQuery(transform_id=transform_id)
        rendered = q.render_query()
        assert transform_id not in rendered
        assert "$transform_ids" in rendered

    def test_render_query_uses_variable_reference_not_literal_for_name(self) -> None:
        transform_id = "my-transform-name"
        q = ComputedAttributeTransformQuery(transform_id=transform_id)
        rendered = q.render_query()
        assert transform_id not in rendered
        assert "$transform_name" in rendered

    def test_get_variables_for_uuid_uses_ids_list(self) -> None:
        transform_id = "12345678-1234-5678-1234-567812345678"
        q = ComputedAttributeTransformQuery(transform_id=transform_id)
        assert q.get_variables() == {"transform_ids": [transform_id]}

    def test_get_variables_for_name_uses_transform_name(self) -> None:
        transform_id = "my-transform-name"
        q = ComputedAttributeTransformQuery(transform_id=transform_id)
        assert q.get_variables() == {"transform_name": transform_id}

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
                                    "commit": {"value": "abc123"},
                                }
                            },
                            "query": {"node": {"id": "query-001", "name": {"value": "tshirt-pitch"}}},
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
            repository_commit="abc123",
            query_name="tshirt-pitch",
        )

    def test_parse_response_returns_none_for_empty_edges(self) -> None:
        """Empty edges is the one shape that means absent, which a caller is allowed to wait out."""
        q = ComputedAttributeTransformQuery(transform_id="txfm-001")
        result = q.parse_response(response={"CoreTransformPython": {"edges": []}})
        assert result is None

    def test_parse_response_raises_for_a_response_of_another_shape(self) -> None:
        """A response the query did not ask for says nothing about whether the transform exists."""
        q = ComputedAttributeTransformQuery(transform_id="txfm-001")
        with pytest.raises(ValueError, match=r"^Unexpected response shape for transform 'txfm-001'$"):
            q.parse_response(response={})

    def test_parse_response_raises_for_a_transform_without_a_repository(self) -> None:
        """A transform whose repository peer is gone is present and unusable, never absent."""
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
                            "repository": {"node": None},
                            "query": {"node": {"id": "query-001", "name": {"value": "my-query"}}},
                        }
                    }
                ]
            }
        }
        with pytest.raises(
            ValueError,
            match=(
                r"^Transform 'txfm-001' is in the database without the repository, "
                r"query or file details a run needs$"
            ),
        ):
            q.parse_response(response=response)

    def test_parse_response_raises_for_unsupported_repository_kind(self) -> None:
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
                                    "__typename": "CoreGenericRepository",
                                    "name": {"value": "my-repo"},
                                    "commit": {"value": "abc123"},
                                }
                            },
                            "query": {"node": {"id": "query-001", "name": {"value": "my-query"}}},
                        }
                    }
                ]
            }
        }
        with pytest.raises(ValueError, match="Unsupported repository kind 'CoreGenericRepository'"):
            q.parse_response(response=response)
