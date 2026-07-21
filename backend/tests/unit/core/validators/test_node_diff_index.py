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
        index.uuids_for_kinds({"TestCar"})


def test_indexes_fields_and_uuids_per_kind() -> None:
    index = NodeDiffIndex()
    index.initialize(
        [
            NodeDiffFieldSummary(
                kind="TestCar",
                attribute_names={"name", "color"},
                relationship_names={"owner"},
                node_uuids={"c1", "c2"},
            ),
            NodeDiffFieldSummary(kind="TestPerson", attribute_names={"height"}, node_uuids={"p1"}),
        ]
    )

    assert index.kinds == {"TestCar", "TestPerson"}
    assert index.has_attribute_diff(kind="TestCar", name="name")
    assert not index.has_attribute_diff(kind="TestCar", name="missing")
    assert not index.has_attribute_diff(kind="Unknown", name="name")
    assert index.has_relationship_diff(kind="TestCar", name="owner")
    assert not index.has_relationship_diff(kind="TestPerson", name="owner")
    assert index.uuids_for_kinds({"TestCar", "TestPerson"}) == {"c1", "c2", "p1"}
    assert index.uuids_for_kinds({"Unknown"}) == set()


def test_summaries_for_same_kind_are_merged() -> None:
    index = NodeDiffIndex()
    index.initialize(
        [
            NodeDiffFieldSummary(kind="TestCar", attribute_names={"name"}, node_uuids={"c1"}),
            NodeDiffFieldSummary(kind="TestCar", attribute_names={"color"}, node_uuids={"c2"}),
        ]
    )

    assert index.has_attribute_diff(kind="TestCar", name="name")
    assert index.has_attribute_diff(kind="TestCar", name="color")
    assert index.uuids_for_kinds({"TestCar"}) == {"c1", "c2"}


def test_initialize_resets_prior_state() -> None:
    index = NodeDiffIndex()
    index.initialize([NodeDiffFieldSummary(kind="A", attribute_names={"x"}, node_uuids={"a1"})])
    index.initialize([NodeDiffFieldSummary(kind="B", attribute_names={"y"}, node_uuids={"b1"})])

    assert index.kinds == {"B"}
    assert not index.has_attribute_diff(kind="A", name="x")
    assert index.uuids_for_kinds({"A"}) == set()


def test_empty_diff() -> None:
    index = NodeDiffIndex()
    index.initialize([])

    assert index.kinds == set()
    assert not index.has_attribute_diff(kind="A", name="x")
    assert index.uuids_for_kinds({"A"}) == set()
