import pytest

from infrahub.actions.constants import BranchScope, ValueMatch


def test_valid_branch_scope() -> None:
    all_branches = BranchScope.from_value(value="all_branches")
    assert all_branches == BranchScope.ALL_BRANCHES


def test_invalid_branch_scope() -> None:
    with pytest.raises(NotImplementedError):
        BranchScope.from_value(value="no_such_option")


def test_invalid_value_match() -> None:
    value_full = ValueMatch.from_value(value="value_full")
    assert value_full == ValueMatch.VALUE_FULL


def test_valid_value_match() -> None:
    with pytest.raises(NotImplementedError):
        ValueMatch.from_value(value="no_such_option")
