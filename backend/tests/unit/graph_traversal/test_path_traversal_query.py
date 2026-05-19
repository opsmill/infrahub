import pytest

from infrahub.graph_traversal.path import PathTraversalQuery


class TestPathTraversalQueryValidation:
    def test_rejects_same_source_and_destination(self) -> None:
        with pytest.raises(ValueError, match="Source and destination nodes must be different"):
            PathTraversalQuery(
                source_id="uuid-1",
                destination_id="uuid-1",
            )

    def test_rejects_max_depth_below_minimum(self) -> None:
        with pytest.raises(ValueError, match="max_depth must be between 1 and 20"):
            PathTraversalQuery(
                source_id="uuid-1",
                destination_id="uuid-2",
                max_depth=0,
            )

    def test_rejects_max_depth_above_maximum(self) -> None:
        with pytest.raises(ValueError, match="max_depth must be between 1 and 20"):
            PathTraversalQuery(
                source_id="uuid-1",
                destination_id="uuid-2",
                max_depth=21,
            )

    def test_rejects_max_paths_below_minimum(self) -> None:
        with pytest.raises(ValueError, match="max_paths must be between 1 and 100"):
            PathTraversalQuery(
                source_id="uuid-1",
                destination_id="uuid-2",
                max_paths=0,
            )

    def test_rejects_max_paths_above_maximum(self) -> None:
        with pytest.raises(ValueError, match="max_paths must be between 1 and 100"):
            PathTraversalQuery(
                source_id="uuid-1",
                destination_id="uuid-2",
                max_paths=101,
            )

    def test_accepts_valid_parameters(self) -> None:
        query = PathTraversalQuery(
            source_id="uuid-1",
            destination_id="uuid-2",
            max_depth=10,
            max_paths=5,
        )
        assert query.source_id == "uuid-1"
        assert query.destination_id == "uuid-2"
        assert query.max_depth == 10
        assert query.max_paths == 5

    def test_default_parameters(self) -> None:
        query = PathTraversalQuery(
            source_id="uuid-1",
            destination_id="uuid-2",
        )
        assert query.max_depth == 5
        assert query.max_paths == 10
        assert query.kind_filter == []
        assert query.relationship_filter == []

    def test_accepts_filters(self) -> None:
        query = PathTraversalQuery(
            source_id="uuid-1",
            destination_id="uuid-2",
            kind_filter=["InfraDevice"],
            relationship_filter=["interfaces"],
        )
        assert query.kind_filter == ["InfraDevice"]
        assert query.relationship_filter == ["interfaces"]
