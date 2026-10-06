from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import Enum

import pytest

from infrahub.pools.intent import FromPoolIntent, FromPoolIntentResolver, FromPoolRequest

POOL_P = "pool-p"
POOL_A = "pool-a"


class _Absent(Enum):
    ABSENT = "absent"


ABSENT = _Absent.ABSENT


@dataclass(frozen=True)
class IntentTestCase:
    name: str
    request: FromPoolRequest
    expected: FromPoolIntent


def _request(
    value: int | _Absent | None = ABSENT,
    from_pool: str | _Absent | None = ABSENT,
    tracked_by: str | None = None,
    held_value: int | None = None,
    held_value_is_default: bool = False,
) -> FromPoolRequest:
    return FromPoolRequest(
        value_present=value is not ABSENT,
        value=None if isinstance(value, _Absent) else value,
        from_pool_present=from_pool is not ABSENT,
        from_pool_id=None if isinstance(from_pool, _Absent) else from_pool,
        held_value_is_default=held_value_is_default,
        tracking_pool_id=tracked_by,
        held_value=held_value,
    )


TABLE_TEST_CASES: list[IntentTestCase] = [
    IntentTestCase(
        name="value_with_pool_untracked_attaches",
        request=_request(value=50, from_pool=POOL_P, held_value=7),
        expected=FromPoolIntent.ATTACH,
    ),
    IntentTestCase(
        name="value_with_pool_untracked_default_attaches",
        request=_request(value=50, from_pool=POOL_P, held_value=7, held_value_is_default=True),
        expected=FromPoolIntent.ATTACH,
    ),
    IntentTestCase(
        name="value_with_pool_untracked_unset_attaches",
        request=_request(value=50, from_pool=POOL_P),
        expected=FromPoolIntent.ATTACH,
    ),
    IntentTestCase(
        name="same_value_with_tracking_pool_attaches",
        request=_request(value=50, from_pool=POOL_P, tracked_by=POOL_P, held_value=50),
        expected=FromPoolIntent.ATTACH,
    ),
    IntentTestCase(
        name="new_value_with_tracking_pool_attaches",
        request=_request(value=50, from_pool=POOL_P, tracked_by=POOL_P, held_value=7),
        expected=FromPoolIntent.ATTACH,
    ),
    IntentTestCase(
        name="value_with_other_pool_re_pools_and_attaches",
        request=_request(value=50, from_pool=POOL_P, tracked_by=POOL_A, held_value=7),
        expected=FromPoolIntent.ATTACH,
    ),
    IntentTestCase(
        name="same_value_with_other_pool_re_pools_and_attaches",
        request=_request(value=50, from_pool=POOL_P, tracked_by=POOL_A, held_value=50),
        expected=FromPoolIntent.ATTACH,
    ),
    IntentTestCase(
        name="value_without_pool_untracked_is_plain_write",
        request=_request(value=50, held_value=7),
        expected=FromPoolIntent.NO_OP,
    ),
    IntentTestCase(
        name="value_without_pool_tracked_is_plain_write",
        request=_request(value=50, tracked_by=POOL_P, held_value=7),
        expected=FromPoolIntent.NO_OP,
    ),
    IntentTestCase(
        name="null_value_with_pool_untracked_discards_and_allocates",
        request=_request(value=None, from_pool=POOL_P, held_value=7),
        expected=FromPoolIntent.ALLOCATE,
    ),
    IntentTestCase(
        name="null_value_with_tracking_pool_discards_and_allocates",
        request=_request(value=None, from_pool=POOL_P, tracked_by=POOL_P, held_value=7),
        expected=FromPoolIntent.ALLOCATE,
    ),
    IntentTestCase(
        name="null_value_with_other_pool_re_pools_and_allocates",
        request=_request(value=None, from_pool=POOL_P, tracked_by=POOL_A, held_value=7),
        expected=FromPoolIntent.ALLOCATE,
    ),
    IntentTestCase(
        name="pool_alone_over_default_allocates",
        request=_request(from_pool=POOL_P, held_value=7, held_value_is_default=True),
        expected=FromPoolIntent.ALLOCATE,
    ),
    IntentTestCase(
        name="pool_alone_over_unset_value_allocates",
        request=_request(from_pool=POOL_P),
        expected=FromPoolIntent.ALLOCATE,
    ),
    IntentTestCase(
        name="pool_alone_over_untracked_number_refuses",
        request=_request(from_pool=POOL_P, held_value=7),
        expected=FromPoolIntent.REFUSE,
    ),
    IntentTestCase(
        name="pool_alone_with_tracking_pool_is_no_op",
        request=_request(from_pool=POOL_P, tracked_by=POOL_P, held_value=7),
        expected=FromPoolIntent.NO_OP,
    ),
    IntentTestCase(
        name="other_pool_alone_over_a_held_number_is_refused",
        request=_request(from_pool=POOL_P, tracked_by=POOL_A, held_value=7),
        expected=FromPoolIntent.REFUSE,
    ),
    IntentTestCase(
        name="other_pool_alone_over_a_default_re_pools_and_allocates",
        request=_request(from_pool=POOL_P, tracked_by=POOL_A, held_value=7, held_value_is_default=True),
        expected=FromPoolIntent.ALLOCATE,
    ),
    IntentTestCase(
        name="null_pool_on_tracked_attribute_detaches",
        request=_request(from_pool=None, tracked_by=POOL_P, held_value=7),
        expected=FromPoolIntent.DETACH,
    ),
    IntentTestCase(
        name="null_pool_with_value_on_tracked_attribute_detaches",
        request=_request(value=50, from_pool=None, tracked_by=POOL_P, held_value=7),
        expected=FromPoolIntent.DETACH,
    ),
    IntentTestCase(
        name="null_pool_with_null_value_on_tracked_attribute_detaches",
        request=_request(value=None, from_pool=None, tracked_by=POOL_P, held_value=7),
        expected=FromPoolIntent.DETACH,
    ),
    IntentTestCase(
        name="null_pool_on_untracked_attribute_is_no_op",
        request=_request(from_pool=None, held_value=7),
        expected=FromPoolIntent.NO_OP,
    ),
    IntentTestCase(
        name="null_pool_with_value_on_untracked_attribute_is_no_op",
        request=_request(value=50, from_pool=None, held_value=7),
        expected=FromPoolIntent.NO_OP,
    ),
    IntentTestCase(
        name="nothing_in_payload_untracked_is_no_op",
        request=_request(held_value=7),
        expected=FromPoolIntent.NO_OP,
    ),
    IntentTestCase(
        name="nothing_in_payload_tracked_is_no_op",
        request=_request(tracked_by=POOL_P, held_value=7),
        expected=FromPoolIntent.NO_OP,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TABLE_TEST_CASES])
def test_resolve_intent(test_case: IntentTestCase) -> None:
    assert FromPoolIntentResolver().resolve(request=test_case.request) == test_case.expected


@dataclass(frozen=True)
class NullVersusAbsentTestCase:
    name: str
    tracked_by: str | None
    held_value: int | None
    absent_value_intent: FromPoolIntent


NULL_VERSUS_ABSENT_TEST_CASES = [
    NullVersusAbsentTestCase(
        name="tracked_by_same_pool", tracked_by=POOL_P, held_value=7, absent_value_intent=FromPoolIntent.NO_OP
    ),
    NullVersusAbsentTestCase(
        name="untracked_hand_set_number", tracked_by=None, held_value=7, absent_value_intent=FromPoolIntent.REFUSE
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in NULL_VERSUS_ABSENT_TEST_CASES])
def test_null_value_allocates_where_an_absent_value_does_not(test_case: NullVersusAbsentTestCase) -> None:
    resolver = FromPoolIntentResolver()
    null_value = resolver.resolve(
        request=_request(value=None, from_pool=POOL_P, tracked_by=test_case.tracked_by, held_value=test_case.held_value)
    )
    absent_value = resolver.resolve(
        request=_request(from_pool=POOL_P, tracked_by=test_case.tracked_by, held_value=test_case.held_value)
    )

    assert null_value == FromPoolIntent.ALLOCATE
    assert absent_value == test_case.absent_value_intent


def test_only_a_pool_named_alone_over_a_held_number_refuses() -> None:
    """Across every class of input, only a pool named alone over a non-default number another pool or none tracks is refused."""
    value_choices: list[int | _Absent | None] = [ABSENT, None, 50, 7]
    from_pool_choices: list[str | _Absent | None] = [ABSENT, None, POOL_P]
    tracked_by_choices: list[str | None] = [None, POOL_P, POOL_A]
    held_choices: list[tuple[int | None, bool]] = [(None, True), (7, True), (7, False)]

    resolver = FromPoolIntentResolver()
    refused = [
        (value, from_pool, tracked_by, current)
        for value, from_pool, tracked_by, current in itertools.product(
            value_choices, from_pool_choices, tracked_by_choices, held_choices
        )
        if resolver.resolve(
            request=_request(
                value=value,
                from_pool=from_pool,
                tracked_by=tracked_by,
                held_value=current[0],
                held_value_is_default=current[1],
            )
        )
        == FromPoolIntent.REFUSE
    ]

    assert refused == [(ABSENT, POOL_P, None, (7, False)), (ABSENT, POOL_P, POOL_A, (7, False))]


@dataclass(frozen=True)
class InvalidRequestTestCase:
    name: str
    value: int | None
    from_pool_id: str | None
    message: str


INVALID_REQUEST_TEST_CASES: list[InvalidRequestTestCase] = [
    InvalidRequestTestCase(
        name="value_without_presence",
        value=50,
        from_pool_id=None,
        message=r"^A value cannot be carried without being present in the payload\.$",
    ),
    InvalidRequestTestCase(
        name="pool_without_presence",
        value=None,
        from_pool_id=POOL_P,
        message=r"^A pool cannot be carried without from_pool being present in the payload\.$",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in INVALID_REQUEST_TEST_CASES])
def test_request_rejects_a_field_carried_without_presence(test_case: InvalidRequestTestCase) -> None:
    with pytest.raises(ValueError, match=test_case.message):
        FromPoolRequest(
            value_present=False,
            value=test_case.value,
            from_pool_present=False,
            from_pool_id=test_case.from_pool_id,
            held_value_is_default=False,
            tracking_pool_id=None,
            held_value=None,
        )
