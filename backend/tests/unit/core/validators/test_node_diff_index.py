import pytest

from infrahub.core.diff.model.path import NodeDiffFieldSummary
from infrahub.core.validators.node_diff_index import NodeDiffIndex


def test_query_before_initialize_raises() -> None:
    index = NodeDiffIndex()

    match = r"^NodeDiffIndex must be initialized with initialize\(\) before its query methods are used$"
    with pytest.raises(RuntimeError, match=match):
        _ = index.kinds
    with pytest.raises(RuntimeError, match=match):
        index.has_attribute_diff(kind="TestCar", name="name")
    with pytest.raises(RuntimeError, match=match):
        index.has_relationship_diff(kind="TestCar", name="owner")
    with pytest.raises(RuntimeError, match=match):
        index.get_uuids_for_attribute(kind="TestCar", name="name")


def test_indexes_fields_and_uuids_per_field() -> None:
    index = NodeDiffIndex()
    index.initialize(
        [
            NodeDiffFieldSummary(
                kind="TestCar",
                attribute_node_uuids={"name": {"c1", "c2"}, "color": {"c1"}},
                relationship_node_uuids={"owner": {"c2"}},
            ),
            NodeDiffFieldSummary(kind="TestPerson", attribute_node_uuids={"height": {"p1"}}),
        ]
    )

    assert index.kinds == {"TestCar", "TestPerson"}
    assert index.has_attribute_diff(kind="TestCar", name="name")
    assert not index.has_attribute_diff(kind="TestCar", name="missing")
    assert not index.has_attribute_diff(kind="Unknown", name="name")
    assert index.has_relationship_diff(kind="TestCar", name="owner")
    assert not index.has_relationship_diff(kind="TestPerson", name="owner")
    # uuids are scoped to the specific field, not merged across the kind
    assert index.get_uuids_for_attribute(kind="TestCar", name="name") == {"c1", "c2"}
    assert index.get_uuids_for_attribute(kind="TestCar", name="color") == {"c1"}
    assert index.get_uuids_for_relationship(kind="TestCar", name="owner") == {"c2"}
    assert index.get_uuids_for_attribute(kind="TestPerson", name="height") == {"p1"}
    assert index.get_uuids_for_attribute(kind="Unknown", name="name") == set()


def test_summaries_for_same_kind_are_merged() -> None:
    index = NodeDiffIndex()
    index.initialize(
        [
            NodeDiffFieldSummary(kind="TestCar", attribute_node_uuids={"name": {"c1"}}),
            NodeDiffFieldSummary(kind="TestCar", attribute_node_uuids={"name": {"c2"}, "color": {"c3"}}),
        ]
    )

    assert index.has_attribute_diff(kind="TestCar", name="name")
    assert index.has_attribute_diff(kind="TestCar", name="color")
    assert index.get_uuids_for_attribute(kind="TestCar", name="name") == {"c1", "c2"}
    assert index.get_uuids_for_attribute(kind="TestCar", name="color") == {"c3"}


def test_initialize_resets_prior_state() -> None:
    index = NodeDiffIndex()
    index.initialize([NodeDiffFieldSummary(kind="A", attribute_node_uuids={"x": {"a1"}})])
    index.initialize([NodeDiffFieldSummary(kind="B", attribute_node_uuids={"y": {"b1"}})])

    assert index.kinds == {"B"}
    assert not index.has_attribute_diff(kind="A", name="x")
    assert index.get_uuids_for_attribute(kind="A", name="x") == set()


def test_empty_diff() -> None:
    index = NodeDiffIndex()
    index.initialize([])

    assert index.kinds == set()
    assert not index.has_attribute_diff(kind="A", name="x")
    assert index.get_uuids_for_attribute(kind="A", name="x") == set()
