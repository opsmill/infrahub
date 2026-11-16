import pytest

from infrahub.constants.database import IndexType
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.graph.index import rel_indexes


@pytest.mark.parametrize("edge_type", list(DatabaseEdgeType), ids=lambda edge_type: edge_type.value)
@pytest.mark.parametrize("edge_property", ["from", "to"])
def test_every_edge_type_is_indexed_on_the_times_it_was_opened_and_closed(
    edge_type: DatabaseEdgeType, edge_property: str
) -> None:
    """A read of the edges opened or closed in a time window needs one range index per edge type and time."""
    matching = [
        index
        for index in rel_indexes
        if index.label == edge_type.value and index.properties == [edge_property] and index.type is IndexType.RANGE
    ]
    assert len(matching) == 1
