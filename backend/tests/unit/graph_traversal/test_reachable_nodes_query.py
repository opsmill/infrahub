import pytest

from infrahub.graph_traversal.reachable import ReachableNodesQuery


class TestReachableNodesQueryValidation:
    def test_rejects_empty_target_kinds(self) -> None:
        with pytest.raises(ValueError, match="At least one target kind is required"):
            ReachableNodesQuery(source_id="uuid-1", target_kinds=[])

    def test_rejects_max_depth_below_minimum(self) -> None:
        with pytest.raises(ValueError, match="max_depth must be between 1 and 20"):
            ReachableNodesQuery(source_id="uuid-1", target_kinds=["InfraDevice"], max_depth=0)

    def test_rejects_max_depth_above_maximum(self) -> None:
        with pytest.raises(ValueError, match="max_depth must be between 1 and 20"):
            ReachableNodesQuery(source_id="uuid-1", target_kinds=["InfraDevice"], max_depth=21)

    def test_rejects_max_results_below_minimum(self) -> None:
        with pytest.raises(ValueError, match="max_results must be between 1 and 200"):
            ReachableNodesQuery(source_id="uuid-1", target_kinds=["InfraDevice"], max_results=0)

    def test_rejects_max_results_above_maximum(self) -> None:
        with pytest.raises(ValueError, match="max_results must be between 1 and 200"):
            ReachableNodesQuery(source_id="uuid-1", target_kinds=["InfraDevice"], max_results=201)

    def test_default_parameters(self) -> None:
        query = ReachableNodesQuery(source_id="uuid-1", target_kinds=["InfraDevice"])
        assert query.max_depth == 5
        assert query.max_results == 50
        assert "Core" in query.excluded_namespaces
