import logging
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.utils import get_fixtures_dir, has_any_key, log_exception_guard


def test_get_fixtures_dir() -> None:
    assert get_fixtures_dir().exists()


def test_log_exception_guard_absorbs_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    log = logging.getLogger("test_log_exception_guard")
    ran_after = False

    with log_exception_guard(log, "block failed"):
        raise RuntimeError("boom")
    ran_after = True

    assert ran_after is True
    assert [record.message for record in caplog.records] == ["block failed"]
    assert caplog.records[0].exc_info is not None


def test_log_exception_guard_no_error_stays_silent(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    log = logging.getLogger("test_log_exception_guard")
    calls: list[str] = []

    with log_exception_guard(log, "block failed"):
        calls.append("ran")

    assert calls == ["ran"]
    assert caplog.records == []


def test_log_exception_guard_isolates_each_iteration(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    log = logging.getLogger("test_log_exception_guard")
    attempted: list[str] = []

    for item in ["a", "b", "c"]:
        with log_exception_guard(log, f"block '{item}' failed"):
            attempted.append(item)
            if item == "b":
                raise RuntimeError("boom")

    assert attempted == ["a", "b", "c"]
    assert [record.message for record in caplog.records] == ["block 'b' failed"]


@dataclass
class HasAnyKeyTestCase:
    name: str
    data: dict[str, Any]
    keys: list[str]
    expected: bool


HAS_ANY_KEY_TEST_CASES: list[HasAnyKeyTestCase] = [
    HasAnyKeyTestCase(
        name="empty_dict_returns_false",
        data={},
        keys=["foo"],
        expected=False,
    ),
    HasAnyKeyTestCase(
        name="empty_keys_returns_false",
        data={"foo": "bar"},
        keys=[],
        expected=False,
    ),
    HasAnyKeyTestCase(
        name="simple_dict_key_found",
        data={"foo": "bar", "baz": "qux"},
        keys=["foo"],
        expected=True,
    ),
    HasAnyKeyTestCase(
        name="simple_dict_key_not_found",
        data={"foo": "bar", "baz": "qux"},
        keys=["missing"],
        expected=False,
    ),
    HasAnyKeyTestCase(
        name="simple_dict_multiple_keys_one_found",
        data={"foo": "bar", "baz": "qux"},
        keys=["missing", "baz"],
        expected=True,
    ),
    HasAnyKeyTestCase(
        name="nested_dict_key_at_top_level",
        data={"foo": {"nested": "value"}, "bar": "baz"},
        keys=["foo"],
        expected=True,
    ),
    HasAnyKeyTestCase(
        name="nested_dict_key_at_second_level",
        data={"foo": {"nested": "value"}, "bar": "baz"},
        keys=["nested"],
        expected=True,
    ),
    HasAnyKeyTestCase(
        name="nested_dict_key_not_found",
        data={"foo": {"nested": "value"}, "bar": "baz"},
        keys=["missing"],
        expected=False,
    ),
    HasAnyKeyTestCase(
        name="deeply_nested_dict_key_found",
        data={"level1": {"level2": {"level3": {"target": "value"}}}},
        keys=["target"],
        expected=True,
    ),
    HasAnyKeyTestCase(
        name="deeply_nested_dict_key_not_found",
        data={"level1": {"level2": {"level3": {"target": "value"}}}},
        keys=["missing"],
        expected=False,
    ),
    HasAnyKeyTestCase(
        name="mixed_nested_dict_multiple_keys",
        data={"a": {"b": {"c": "value"}}, "d": "value"},
        keys=["c", "x", "y"],
        expected=True,
    ),
    HasAnyKeyTestCase(
        name="dict_with_non_dict_values",
        data={"foo": [1, 2, 3], "bar": 42, "baz": "string"},
        keys=["foo"],
        expected=True,
    ),
    HasAnyKeyTestCase(
        name="nested_dict_with_list_value_key_in_dict",
        data={"foo": {"bar": [1, 2, 3]}, "baz": "qux"},
        keys=["bar"],
        expected=True,
    ),
    HasAnyKeyTestCase(
        name="search_key_matches_value_not_key",
        data={"foo": "target"},
        keys=["target"],
        expected=False,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in HAS_ANY_KEY_TEST_CASES],
)
def test_has_any_key(test_case: HasAnyKeyTestCase) -> None:
    """Test that has_any_key correctly identifies if any key exists in the dictionary."""
    result = has_any_key(data=test_case.data, keys=test_case.keys)
    assert result == test_case.expected
