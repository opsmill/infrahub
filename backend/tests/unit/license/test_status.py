from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from infrahub.license.models import License, LicenseFailure, LicenseFailureReason, LicenseState, LicenseStatus
from infrahub.license.status import evaluate
from tests.adapters.license import build_license

STARTS_AT = datetime(2026, 1, 1, tzinfo=UTC)
ENDS_AT = datetime(2027, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _build_license(license_type: str = "commercial") -> License:
    return build_license(license_type=license_type, starts_at=STARTS_AT, ends_at=ENDS_AT)


def test_no_license_is_unlicensed() -> None:
    assert evaluate(outcome=None, now=NOW) == LicenseStatus(state=LicenseState.UNLICENSED)


@pytest.mark.parametrize("reason", list(LicenseFailureReason))
def test_failed_verification_is_invalid_with_its_reason(reason: LicenseFailureReason) -> None:
    assert evaluate(outcome=LicenseFailure(reason=reason), now=NOW) == LicenseStatus(
        state=LicenseState.INVALID, reason=reason
    )


@dataclass
class BoundaryTestCase:
    name: str
    now: datetime
    expected_state: LicenseState
    expected_days_remaining: int | None
    expected_days_since_expiry: int | None


BOUNDARY_TEST_CASES: list[BoundaryTestCase] = [
    BoundaryTestCase(
        name="one_second_before_start_is_not_yet_valid",
        now=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        expected_state=LicenseState.NOT_YET_VALID,
        expected_days_remaining=366,
        expected_days_since_expiry=None,
    ),
    BoundaryTestCase(
        name="at_start_is_valid",
        now=datetime(2026, 1, 1, tzinfo=UTC),
        expected_state=LicenseState.VALID,
        expected_days_remaining=365,
        expected_days_since_expiry=None,
    ),
    BoundaryTestCase(
        name="one_second_before_the_last_30_days_is_valid",
        now=datetime(2026, 12, 1, 23, 59, 59, tzinfo=UTC),
        expected_state=LicenseState.VALID,
        expected_days_remaining=31,
        expected_days_since_expiry=None,
    ),
    BoundaryTestCase(
        name="at_the_start_of_the_last_30_days_is_expiring",
        now=datetime(2026, 12, 2, tzinfo=UTC),
        expected_state=LicenseState.EXPIRING,
        expected_days_remaining=30,
        expected_days_since_expiry=None,
    ),
    BoundaryTestCase(
        name="one_second_before_end_is_expiring",
        now=datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
        expected_state=LicenseState.EXPIRING,
        expected_days_remaining=1,
        expected_days_since_expiry=None,
    ),
    BoundaryTestCase(
        name="at_end_is_expired",
        now=datetime(2027, 1, 1, tzinfo=UTC),
        expected_state=LicenseState.EXPIRED,
        expected_days_remaining=None,
        expected_days_since_expiry=0,
    ),
]


@pytest.mark.parametrize("license_type", ["evaluation", "commercial", "partner"])
@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in BOUNDARY_TEST_CASES])
def test_state_at_each_boundary_is_the_same_for_every_license_type(
    test_case: BoundaryTestCase, license_type: str
) -> None:
    granted = _build_license(license_type=license_type)

    assert evaluate(outcome=granted, now=test_case.now) == LicenseStatus(
        state=test_case.expected_state,
        license=granted,
        days_remaining=test_case.expected_days_remaining,
        days_since_expiry=test_case.expected_days_since_expiry,
    )


def test_days_remaining_rounds_up_a_partial_day() -> None:
    granted = _build_license()

    status = evaluate(outcome=granted, now=datetime(2026, 12, 20, 12, 0, tzinfo=UTC))

    assert status == LicenseStatus(state=LicenseState.EXPIRING, license=granted, days_remaining=12)


def test_days_since_expiry_rounds_down_a_partial_day() -> None:
    granted = _build_license()

    status = evaluate(outcome=granted, now=datetime(2027, 1, 4, 21, 36, tzinfo=UTC))

    assert status == LicenseStatus(state=LicenseState.EXPIRED, license=granted, days_since_expiry=3)
