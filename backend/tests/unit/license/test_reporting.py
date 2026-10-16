from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from infrahub.license.models import License, LicenseFailureReason, LicenseState, LicenseStatus
from infrahub.license.reporting import log_license_state
from tests.adapters.license import FailingLicenseService, RecordingLicenseService

LICENSE = License(
    license_id="lic-0042",
    customer_name="Example Networks",
    license_type="commercial",
    product_tier="enterprise",
    support_tier="premium",
    starts_at=datetime(2026, 1, 1, tzinfo=UTC),
    ends_at=datetime(2027, 1, 1, tzinfo=UTC),
    issued_at=datetime(2025, 12, 15, tzinfo=UTC),
    issuer="opsmill-test",
)
LICENSE_FIELDS = {
    "license_id": "lic-0042",
    "license_type": "commercial",
    "license_starts_at": "2026-01-01T00:00:00+00:00",
    "license_ends_at": "2027-01-01T00:00:00+00:00",
}


def _logged_payloads(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [
        {name: value for name, value in record.msg.items() if name != "timestamp"}
        for record in caplog.records
        if record.name == "infrahub" and isinstance(record.msg, dict)
    ]


@dataclass
class StartupLineCase:
    name: str
    status: LicenseStatus
    key_is_set: bool
    expected: dict[str, Any]
    """The whole logged payload apart from its timestamp, so any extra field fails the comparison."""


STARTUP_LINE_CASES: list[StartupLineCase] = [
    StartupLineCase(
        name="not_required_without_key",
        status=LicenseStatus(state=LicenseState.NOT_REQUIRED),
        key_is_set=False,
        expected={
            "event": "No license is required for this deployment",
            "level": "info",
            "logger": "infrahub",
            "license_state": "not_required",
        },
    ),
    StartupLineCase(
        name="not_required_with_key_reports_the_key_as_ignored",
        status=LicenseStatus(state=LicenseState.NOT_REQUIRED),
        key_is_set=True,
        expected={
            "event": "A license key is set but ignored, because this deployment does not require a license",
            "level": "info",
            "logger": "infrahub",
            "license_state": "not_required",
        },
    ),
    StartupLineCase(
        name="valid",
        status=LicenseStatus(state=LicenseState.VALID, license=LICENSE, days_remaining=200),
        key_is_set=True,
        expected={
            "event": "License is valid",
            "level": "info",
            "logger": "infrahub",
            "license_state": "valid",
            **LICENSE_FIELDS,
            "license_days_remaining": 200,
        },
    ),
    StartupLineCase(
        name="expiring",
        status=LicenseStatus(state=LicenseState.EXPIRING, license=LICENSE, days_remaining=12),
        key_is_set=True,
        expected={
            "event": "License expires soon; set a renewed license in INFRAHUB_LICENSE_KEY on every API server "
            "and task worker",
            "level": "warning",
            "logger": "infrahub",
            "license_state": "expiring",
            **LICENSE_FIELDS,
            "license_days_remaining": 12,
        },
    ),
    StartupLineCase(
        name="expired",
        status=LicenseStatus(state=LicenseState.EXPIRED, license=LICENSE, days_since_expiry=3),
        key_is_set=True,
        expected={
            "event": "License has expired; set a renewed license in INFRAHUB_LICENSE_KEY on every API server "
            "and task worker",
            "level": "warning",
            "logger": "infrahub",
            "license_state": "expired",
            **LICENSE_FIELDS,
            "license_days_since_expiry": 3,
        },
    ),
    StartupLineCase(
        name="not_yet_valid",
        status=LicenseStatus(state=LicenseState.NOT_YET_VALID, license=LICENSE, days_remaining=400),
        key_is_set=True,
        expected={
            "event": "License is not valid yet; check its start date and the server clock",
            "level": "warning",
            "logger": "infrahub",
            "license_state": "not_yet_valid",
            **LICENSE_FIELDS,
            "license_days_remaining": 400,
        },
    ),
    StartupLineCase(
        name="unlicensed",
        status=LicenseStatus(state=LicenseState.UNLICENSED),
        key_is_set=False,
        expected={
            "event": "No license is set; set INFRAHUB_LICENSE_KEY on every API server and task worker",
            "level": "warning",
            "logger": "infrahub",
            "license_state": "unlicensed",
        },
    ),
    StartupLineCase(
        name="invalid_names_the_reason",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.BAD_SIGNATURE),
        key_is_set=True,
        expected={
            "event": "License could not be verified; check INFRAHUB_LICENSE_KEY on every API server and task worker",
            "level": "error",
            "logger": "infrahub",
            "license_state": "invalid",
            "license_reason": "bad_signature",
        },
    ),
    StartupLineCase(
        name="invalid_from_an_internal_error_points_at_the_earlier_error",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.INTERNAL_ERROR),
        key_is_set=True,
        expected={
            "event": "License state could not be determined because of an internal error; see the error logged before",
            "level": "error",
            "logger": "infrahub",
            "license_state": "invalid",
            "license_reason": "internal_error",
        },
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in STARTUP_LINE_CASES])
def test_log_license_state_logs_one_line_at_the_level_of_the_state(
    caplog: pytest.LogCaptureFixture, test_case: StartupLineCase
) -> None:
    with caplog.at_level("INFO", logger="infrahub"):
        log_license_state(service=RecordingLicenseService(status=test_case.status), key_is_set=test_case.key_is_set)

    assert _logged_payloads(caplog) == [test_case.expected]


def test_log_license_state_reports_a_failing_service_as_invalid_without_raising(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The traceback entry and the state line are both kept, so every process logs its state exactly once."""
    with caplog.at_level("INFO", logger="infrahub"):
        log_license_state(service=FailingLicenseService(), key_is_set=True)

    traceback_line, state_line = _logged_payloads(caplog)
    assert (traceback_line["level"], traceback_line["event"], traceback_line["exc_info"]) == (
        "error",
        "The license service failed; reporting the license as invalid with reason internal_error",
        True,
    )
    assert state_line == {
        "event": "License state could not be determined because of an internal error; see the error logged before",
        "level": "error",
        "logger": "infrahub",
        "license_state": "invalid",
        "license_reason": "internal_error",
    }
