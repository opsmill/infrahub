from __future__ import annotations

from infrahub.pools.number_ranges import PoolRange
from infrahub.pools.range_refusal import (
    BranchValue,
    other_branch_refusal,
    tracked_edit_refusal,
    tracked_empty_refusal,
    tracked_reset_refusal,
    untracked_attach_refusal,
)

ATTRIBUTE_ID = "18a0b9e3-0000-0000-0000-00000000dddd"
LOW_RANGE = PoolRange(id="low", start=1, end=100)
HIGH_RANGE = PoolRange(id="high", start=200, end=300)


def test_an_attach_outside_the_ranges_lists_every_range_sorted_by_start() -> None:
    message = untracked_attach_refusal(
        pool_name="tickets", attribute_name="ticket_id", ranges=[HIGH_RANGE, LOW_RANGE], value=900
    )

    assert message == (
        "The tickets pool cannot track 900 on 'ticket_id', because 900 is outside its ranges: 1-100, 200-300. "
        "Send a number inside those ranges."
    )


def test_an_attach_to_a_pool_without_ranges_says_it_has_none() -> None:
    message = untracked_attach_refusal(pool_name="tickets", attribute_name="ticket_id", ranges=[], value=5)

    assert message == (
        "The tickets pool cannot track 5 on 'ticket_id', because 5 is outside its ranges: no ranges. "
        "Send a number inside those ranges."
    )


def test_an_edit_of_a_tracked_number_outside_the_ranges_explains_how_to_stop_tracking() -> None:
    message = tracked_edit_refusal(
        pool_name="tickets", attribute_name="ticket_id", ranges=[HIGH_RANGE, LOW_RANGE], value=900
    )

    assert message == (
        "'ticket_id' is tracked by the tickets pool, so it cannot hold 900, which is outside the pool's ranges: "
        "1-100, 200-300. To set 900 and stop the pool tracking 'ticket_id', "
        "send 'value: 900' together with 'from_pool: null'."
    )


def test_an_edit_of_a_tracked_number_on_a_pool_without_ranges_says_it_has_none() -> None:
    message = tracked_edit_refusal(pool_name="tickets", attribute_name="ticket_id", ranges=[], value=5)

    assert message == (
        "'ticket_id' is tracked by the tickets pool, so it cannot hold 5, which is outside the pool's ranges: "
        "no ranges. To set 5 and stop the pool tracking 'ticket_id', send 'value: 5' together with 'from_pool: null'."
    )


def test_emptying_a_tracked_number_explains_how_to_stop_tracking() -> None:
    assert tracked_empty_refusal(pool_name="tickets", attribute_name="ticket_id") == (
        "'ticket_id' is tracked by the tickets pool, so it cannot be emptied. To empty 'ticket_id' and stop the pool "
        "tracking it, send 'value: null' together with 'from_pool: null'."
    )


def test_a_reset_of_a_tracked_number_names_the_pool_and_the_null_pool_reset() -> None:
    assert tracked_reset_refusal(pool_name="tickets", attribute_name="ticket_id") == (
        "'ticket_id' is tracked by the tickets pool, so it cannot be reset to its default. To reset 'ticket_id' and "
        "stop the pool tracking it, send 'is_default: true' together with 'from_pool: null'."
    )


def test_other_branches_holding_numbers_inside_the_ranges_are_not_refused() -> None:
    branch_values = [
        BranchValue(attribute_id=ATTRIBUTE_ID, branch="main", value=1),
        BranchValue(attribute_id=ATTRIBUTE_ID, branch="feature", value=250),
    ]

    assert (
        other_branch_refusal(
            pool_name="tickets", attribute_name="ticket_id", ranges=[LOW_RANGE, HIGH_RANGE], branch_values=branch_values
        )
        is None
    )


def test_no_other_branch_value_is_not_refused() -> None:
    assert (
        other_branch_refusal(pool_name="tickets", attribute_name="ticket_id", ranges=[LOW_RANGE], branch_values=[])
        is None
    )


def test_every_branch_holding_a_number_outside_the_ranges_is_listed_sorted_by_name() -> None:
    branch_values = [
        BranchValue(attribute_id=ATTRIBUTE_ID, branch="zeta", value=900),
        BranchValue(attribute_id=ATTRIBUTE_ID, branch="main", value=50),
        BranchValue(attribute_id=ATTRIBUTE_ID, branch="alpha", value=150),
        BranchValue(attribute_id=ATTRIBUTE_ID, branch="beta", value=1000),
    ]

    message = other_branch_refusal(
        pool_name="tickets", attribute_name="ticket_id", ranges=[HIGH_RANGE, LOW_RANGE], branch_values=branch_values
    )

    assert message == (
        "The tickets pool cannot track 'ticket_id', because a pool tracks an attribute on every branch and "
        "branch 'alpha' holds 150, branch 'beta' holds 1000, branch 'zeta' holds 900 outside its ranges: "
        "1-100, 200-300. Change the number on that branch, or delete the branch, before attaching to or allocating from this pool."
    )


def test_a_branch_value_on_a_pool_without_ranges_is_refused_and_says_it_has_none() -> None:
    message = other_branch_refusal(
        pool_name="tickets",
        attribute_name="ticket_id",
        ranges=[],
        branch_values=[BranchValue(attribute_id=ATTRIBUTE_ID, branch="main", value=5)],
    )

    assert message == (
        "The tickets pool cannot track 'ticket_id', because a pool tracks an attribute on every branch and "
        "branch 'main' holds 5 outside its ranges: no ranges. "
        "Change the number on that branch, or delete the branch, before attaching to or allocating from this pool."
    )
