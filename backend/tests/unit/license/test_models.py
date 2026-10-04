from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from infrahub.license.models import License


def _build_license(**overrides: Any) -> License:
    fields: dict[str, Any] = {
        "license_id": "lic-0001",
        "customer_name": "Example Networks",
        "license_type": "commercial",
        "product_tier": "enterprise",
        "support_tier": "premium",
        "starts_at": datetime(2026, 1, 1, tzinfo=UTC),
        "ends_at": datetime(2027, 1, 1, tzinfo=UTC),
        "issued_at": datetime(2025, 12, 15, tzinfo=UTC),
        "issuer": "opsmill",
    }
    fields.update(overrides)
    return License(**fields)


def test_aware_datetimes_are_normalized_to_utc() -> None:
    athens = timezone(timedelta(hours=2))

    granted = _build_license(
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
        _build_license(**{field_name: naive})


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
        _build_license(starts_at=datetime(2026, 1, 1, tzinfo=UTC), ends_at=test_case.ends_at)


def test_unknown_license_type_is_kept_as_received() -> None:
    granted = _build_license(license_type="partner")

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
    assert _build_license(license_type=test_case.license_type).is_evaluation is test_case.expected
