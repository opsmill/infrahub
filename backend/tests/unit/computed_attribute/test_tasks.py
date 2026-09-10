from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.computed_attribute.tasks import _belongs_to_query, _partition_transform_results
from infrahub.core.query_group.subscribers import SubscriberRef
from infrahub.core.recompute.bulk_write import AttributeValueWrite


def _write(node_id: str, value: Any) -> AttributeValueWrite:
    return AttributeValueWrite(node_id=node_id, field="desc", value=value)


def test_partition_transform_results_persists_only_string_values() -> None:
    """A string value is persisted; a None or non-string value is skipped so the prior value stays."""
    ok = _write("n1", "hello")
    null_value = _write("n2", None)
    wrong_type = _write("n3", 42)

    writes, skipped = _partition_transform_results([("n1", ok), ("n2", null_value), ("n3", wrong_type)])

    assert writes == [ok]
    reasons = dict(skipped)
    assert list(reasons) == ["n2", "n3"]
    assert "NoneType" in reasons["n2"]
    assert "int" in reasons["n3"]


def test_partition_transform_results_isolates_a_failed_node() -> None:
    """A node whose transform raised is skipped without dropping the healthy nodes' writes."""
    ok1 = _write("n1", "a")
    ok2 = _write("n3", "b")

    writes, skipped = _partition_transform_results([("n1", ok1), ("n2", RuntimeError("boom")), ("n3", ok2)])

    assert writes == [ok1, ok2]
    assert len(skipped) == 1
    assert skipped[0][0] == "n2"
    assert "boom" in skipped[0][1]


def test_partition_transform_results_handles_empty() -> None:
    assert _partition_transform_results([]) == ([], [])


@dataclass
class QueryMatchCase:
    name: str
    group_query_id: str | None
    automation_query_id: str | None
    expected: bool


QUERY_MATCH_CASES = [
    QueryMatchCase(
        name="the_same_query_matches", group_query_id="query01", automation_query_id="query01", expected=True
    ),
    QueryMatchCase(
        name="another_query_is_dropped", group_query_id="query02", automation_query_id="query01", expected=False
    ),
    QueryMatchCase(
        name="a_group_with_no_query_is_kept", group_query_id=None, automation_query_id="query01", expected=True
    ),
    QueryMatchCase(
        name="an_automation_with_no_query_keeps_every_group",
        group_query_id="query02",
        automation_query_id=None,
        expected=True,
    ),
]


@pytest.mark.parametrize("case", QUERY_MATCH_CASES, ids=lambda case: case.name)
def test_belongs_to_query(case: QueryMatchCase) -> None:
    """A subscriber is dropped only when both queries are known and differ."""
    ref = SubscriberRef(id="n1", kind="TestCar", query_id=case.group_query_id)

    assert _belongs_to_query(ref=ref, graphql_query_id=case.automation_query_id) is case.expected
