from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from infrahub.license.models import LicenseFailureReason, LicenseState, LicenseStatus
from tests.adapters.license import build_license


def test_aware_datetimes_are_normalized_to_utc() -> None:
    athens = timezone(timedelta(hours=2))

    granted = build_license(
        starts_at=datetime(2026, 1, 1, 2, 0, tzinfo=athens),
        ends_at=datetime(2027, 1, 1, 2, 0, tzinfo=athens),
        issued_at=datetime(2025, 12, 15, 2, 0, tzinfo=athens),
    )

    assert granted.starts_at == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert granted.ends_at == datetime(2027, 1, 1, 0, 0, tzinfo=UTC)
    assert granted.issued_at == datetime(2025, 12, 15, 0, 0, tzinfo=UTC)
    assert granted.starts_at.tzinfo is UTC
    assert granted.ends_at.tzinfo is UTC
    assert granted.issued_at.tzinfo is UTC


@pytest.mark.parametrize("field_name", ["starts_at", "ends_at", "issued_at"])
def test_naive_datetime_is_rejected(field_name: str) -> None:
    naive = datetime(2026, 6, 1)  # noqa: DTZ001

    with pytest.raises(ValueError, match=rf"^License '{field_name}' must be timezone-aware, got 2026-06-01T00:00:00$"):
        build_license(**{field_name: naive})


@dataclass
class EndNotAfterStartTestCase:
    name: str
    ends_at: datetime
    expected_message: str


END_NOT_AFTER_START_TEST_CASES: list[EndNotAfterStartTestCase] = [
    EndNotAfterStartTestCase(
        name="ends_at_start",
        ends_at=datetime(2026, 1, 1, tzinfo=UTC),
        expected_message=(
            "License 'ends_at' must be later than 'starts_at', "
            "got starts_at=2026-01-01T00:00:00+00:00 ends_at=2026-01-01T00:00:00+00:00"
        ),
    ),
    EndNotAfterStartTestCase(
        name="ends_before_start",
        ends_at=datetime(2025, 12, 31, tzinfo=UTC),
        expected_message=(
            "License 'ends_at' must be later than 'starts_at', "
            "got starts_at=2026-01-01T00:00:00+00:00 ends_at=2025-12-31T00:00:00+00:00"
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in END_NOT_AFTER_START_TEST_CASES])
def test_license_must_end_after_it_starts(test_case: EndNotAfterStartTestCase) -> None:
    with pytest.raises(ValueError, match=rf"^{re.escape(test_case.expected_message)}$"):
        build_license(starts_at=datetime(2026, 1, 1, tzinfo=UTC), ends_at=test_case.ends_at)


def test_unknown_license_type_is_kept_as_received() -> None:
    granted = build_license(license_type="partner")

    assert granted.license_type == "partner"
    assert granted.is_evaluation is False


@dataclass
class IsEvaluationTestCase:
    name: str
    license_type: str
    expected: bool


IS_EVALUATION_TEST_CASES: list[IsEvaluationTestCase] = [
    IsEvaluationTestCase(name="evaluation", license_type="evaluation", expected=True),
    IsEvaluationTestCase(name="commercial", license_type="commercial", expected=False),
    IsEvaluationTestCase(name="different_case", license_type="Evaluation", expected=False),
    IsEvaluationTestCase(name="unknown_type", license_type="partner", expected=False),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in IS_EVALUATION_TEST_CASES])
def test_is_evaluation_only_for_the_evaluation_type(test_case: IsEvaluationTestCase) -> None:
    assert build_license(license_type=test_case.license_type).is_evaluation is test_case.expected


TEXT_FIELDS = ["license_id", "customer_name", "license_type", "product_tier", "support_tier", "issuer"]


@pytest.mark.parametrize("field_name", TEXT_FIELDS)
def test_non_text_field_is_rejected(field_name: str) -> None:
    with pytest.raises(ValueError, match=rf"^License '{field_name}' must be a string, got int$"):
        build_license(**{field_name: 3})


@pytest.mark.parametrize("field_name", ["starts_at", "ends_at", "issued_at"])
def test_non_datetime_field_is_rejected(field_name: str) -> None:
    with pytest.raises(ValueError, match=rf"^License '{field_name}' must be a datetime, got int$"):
        build_license(**{field_name: 1767225600})


@dataclass
class RejectedStatusTestCase:
    name: str
    state: LicenseState
    details: dict[str, Any]
    expected_message: str


GRANTED = build_license()

REJECTED_STATUS_TEST_CASES: list[RejectedStatusTestCase] = [
    RejectedStatusTestCase(
        name="invalid_without_reason",
        state=LicenseState.INVALID,
        details={},
        expected_message="License status 'invalid' must set exactly ['reason'], got []",
    ),
    RejectedStatusTestCase(
        name="invalid_with_license",
        state=LicenseState.INVALID,
        details={"reason": LicenseFailureReason.WRONG_PRODUCT, "license": GRANTED},
        expected_message="License status 'invalid' must set exactly ['reason'], got ['license', 'reason']",
    ),
    RejectedStatusTestCase(
        name="invalid_with_days_remaining",
        state=LicenseState.INVALID,
        details={"reason": LicenseFailureReason.BAD_SIGNATURE, "days_remaining": 10},
        expected_message="License status 'invalid' must set exactly ['reason'], got ['days_remaining', 'reason']",
    ),
    RejectedStatusTestCase(
        name="unlicensed_with_reason",
        state=LicenseState.UNLICENSED,
        details={"reason": LicenseFailureReason.MALFORMED},
        expected_message="License status 'unlicensed' must set exactly [], got ['reason']",
    ),
    RejectedStatusTestCase(
        name="unlicensed_with_license",
        state=LicenseState.UNLICENSED,
        details={"license": GRANTED},
        expected_message="License status 'unlicensed' must set exactly [], got ['license']",
    ),
    RejectedStatusTestCase(
        name="not_required_with_days_since_expiry",
        state=LicenseState.NOT_REQUIRED,
        details={"days_since_expiry": 0},
        expected_message="License status 'not_required' must set exactly [], got ['days_since_expiry']",
    ),
    RejectedStatusTestCase(
        name="valid_without_license",
        state=LicenseState.VALID,
        details={"days_remaining": 200},
        expected_message=(
            "License status 'valid' must set exactly ['days_remaining', 'license'], got ['days_remaining']"
        ),
    ),
    RejectedStatusTestCase(
        name="valid_without_days_remaining",
        state=LicenseState.VALID,
        details={"license": GRANTED},
        expected_message="License status 'valid' must set exactly ['days_remaining', 'license'], got ['license']",
    ),
    RejectedStatusTestCase(
        name="valid_with_reason",
        state=LicenseState.VALID,
        details={"reason": LicenseFailureReason.UNKNOWN_KEY, "license": GRANTED, "days_remaining": 200},
        expected_message=(
            "License status 'valid' must set exactly ['days_remaining', 'license'], "
            "got ['days_remaining', 'license', 'reason']"
        ),
    ),
    RejectedStatusTestCase(
        name="expiring_without_days_remaining",
        state=LicenseState.EXPIRING,
        details={"license": GRANTED},
        expected_message="License status 'expiring' must set exactly ['days_remaining', 'license'], got ['license']",
    ),
    RejectedStatusTestCase(
        name="expiring_with_days_since_expiry",
        state=LicenseState.EXPIRING,
        details={"license": GRANTED, "days_remaining": 12, "days_since_expiry": 0},
        expected_message=(
            "License status 'expiring' must set exactly ['days_remaining', 'license'], "
            "got ['days_remaining', 'days_since_expiry', 'license']"
        ),
    ),
    RejectedStatusTestCase(
        name="not_yet_valid_without_license",
        state=LicenseState.NOT_YET_VALID,
        details={"days_remaining": 400},
        expected_message=(
            "License status 'not_yet_valid' must set exactly ['days_remaining', 'license'], got ['days_remaining']"
        ),
    ),
    RejectedStatusTestCase(
        name="not_yet_valid_without_days_remaining",
        state=LicenseState.NOT_YET_VALID,
        details={"license": GRANTED},
        expected_message=(
            "License status 'not_yet_valid' must set exactly ['days_remaining', 'license'], got ['license']"
        ),
    ),
    RejectedStatusTestCase(
        name="expired_without_license",
        state=LicenseState.EXPIRED,
        details={"days_since_expiry": 3},
        expected_message=(
            "License status 'expired' must set exactly ['days_since_expiry', 'license'], got ['days_since_expiry']"
        ),
    ),
    RejectedStatusTestCase(
        name="expired_without_days_since_expiry",
        state=LicenseState.EXPIRED,
        details={"license": GRANTED},
        expected_message="License status 'expired' must set exactly ['days_since_expiry', 'license'], got ['license']",
    ),
    RejectedStatusTestCase(
        name="expired_with_days_remaining",
        state=LicenseState.EXPIRED,
        details={"license": GRANTED, "days_remaining": 1},
        expected_message=(
            "License status 'expired' must set exactly ['days_since_expiry', 'license'], "
            "got ['days_remaining', 'license']"
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REJECTED_STATUS_TEST_CASES])
def test_status_with_a_missing_or_an_extra_detail_is_rejected(test_case: RejectedStatusTestCase) -> None:
    with pytest.raises(ValueError, match=rf"^{re.escape(test_case.expected_message)}$"):
        LicenseStatus(state=test_case.state, **test_case.details)
