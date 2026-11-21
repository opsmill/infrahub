from __future__ import annotations

from typing import Any

import pytest

from infrahub.core.constants import NULL_VALUE, DiffAction, RelationshipStatus
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.query_parser import DiffPropertyIntermediate, DiffValueIntermediate
from infrahub.core.timestamp import Timestamp


def _property_with_values(earlier: Any, later: Any, from_time: Timestamp) -> DiffPropertyIntermediate:
    diff_property = DiffPropertyIntermediate(property_type=DatabaseEdgeType.HAS_VALUE)
    diff_property.add_value(
        DiffValueIntermediate(changed_at=from_time.add(seconds=-10), status=RelationshipStatus.ACTIVE, value=earlier)
    )
    diff_property.add_value(
        DiffValueIntermediate(changed_at=from_time.add(seconds=10), status=RelationshipStatus.ACTIVE, value=later)
    )
    return diff_property


@pytest.mark.parametrize(
    ("earlier", "later", "expected_action", "expected_new"),
    [
        pytest.param(NULL_VALUE, ["a", "b"], DiffAction.ADDED, ["a", "b"], id="list-added"),
        pytest.param(["a", "b"], NULL_VALUE, DiffAction.REMOVED, NULL_VALUE, id="list-removed"),
        pytest.param(NULL_VALUE, {"key": "value"}, DiffAction.ADDED, {"key": "value"}, id="dict-added"),
        pytest.param({"key": "value"}, NULL_VALUE, DiffAction.REMOVED, NULL_VALUE, id="dict-removed"),
        pytest.param(["a"], ["b"], DiffAction.UPDATED, ["b"], id="list-updated"),
        pytest.param({"k": 1}, {"k": 2}, DiffAction.UPDATED, {"k": 2}, id="dict-updated"),
        pytest.param(None, "text", DiffAction.ADDED, "text", id="str-added"),
        pytest.param("text", NULL_VALUE, DiffAction.REMOVED, NULL_VALUE, id="str-removed"),
    ],
)
def test_property_details_with_unhashable_values(
    earlier: Any, later: Any, expected_action: DiffAction, expected_new: Any
) -> None:
    from_time = Timestamp()
    diff_property = _property_with_values(earlier=earlier, later=later, from_time=from_time)

    action, _, previous_value, new_value = diff_property.get_property_details(from_time=from_time)

    assert action is expected_action
    assert previous_value == earlier
    assert new_value == expected_new
