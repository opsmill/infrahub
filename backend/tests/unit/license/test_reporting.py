from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from infrahub.license.models import License, LicenseFailureReason, LicenseState, LicenseStatus, NoticeMode
from infrahub.license.reporting import license_block, license_report_lines, log_license_state
from tests.adapters.license import FailingLicenseService, RecordingLicenseService
from tests.helpers.log import infrahub_log_payloads

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

    assert infrahub_log_payloads(caplog) == [test_case.expected]


def test_log_license_state_reports_a_failing_service_as_invalid_without_raising(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The traceback entry and the state line are both kept, so every process logs its state exactly once."""
    with caplog.at_level("INFO", logger="infrahub"):
        log_license_state(service=FailingLicenseService(), key_is_set=True)

    traceback_line, state_line = infrahub_log_payloads(caplog)
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


STATE_ONLY_BLOCK_FIELDS = {
    "license_id": None,
    "license_type": None,
    "product_tier": None,
    "support_tier": None,
    "starts_at": None,
    "ends_at": None,
    "issuer": None,
}
LICENSE_BLOCK_FIELDS = {
    "license_id": "lic-0042",
    "license_type": "commercial",
    "product_tier": "enterprise",
    "support_tier": "premium",
    "starts_at": "2026-01-01T00:00:00Z",
    "ends_at": "2027-01-01T00:00:00Z",
    "issuer": "opsmill-test",
}


@dataclass
class TelemetryBlockCase:
    name: str
    status: LicenseStatus
    expected: dict[str, Any] | None
    """The whole block as serialized into the snapshot, so any extra field fails the comparison."""


TELEMETRY_BLOCK_CASES: list[TelemetryBlockCase] = [
    TelemetryBlockCase(
        name="not_required_has_no_block",
        status=LicenseStatus(state=LicenseState.NOT_REQUIRED),
        expected=None,
    ),
    TelemetryBlockCase(
        name="unlicensed_carries_the_state_only",
        status=LicenseStatus(state=LicenseState.UNLICENSED),
        expected={"state": "unlicensed", **STATE_ONLY_BLOCK_FIELDS},
    ),
    TelemetryBlockCase(
        name="invalid_carries_the_state_only",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.BAD_SIGNATURE),
        expected={"state": "invalid", **STATE_ONLY_BLOCK_FIELDS},
    ),
    TelemetryBlockCase(
        name="invalid_from_an_internal_error_carries_the_state_only",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.INTERNAL_ERROR),
        expected={"state": "invalid", **STATE_ONLY_BLOCK_FIELDS},
    ),
    TelemetryBlockCase(
        name="valid_carries_every_license_field",
        status=LicenseStatus(state=LicenseState.VALID, license=LICENSE, days_remaining=200),
        expected={"state": "valid", **LICENSE_BLOCK_FIELDS},
    ),
    TelemetryBlockCase(
        name="expiring_carries_every_license_field",
        status=LicenseStatus(state=LicenseState.EXPIRING, license=LICENSE, days_remaining=12),
        expected={"state": "expiring", **LICENSE_BLOCK_FIELDS},
    ),
    TelemetryBlockCase(
        name="expired_carries_every_license_field",
        status=LicenseStatus(state=LicenseState.EXPIRED, license=LICENSE, days_since_expiry=3),
        expected={"state": "expired", **LICENSE_BLOCK_FIELDS},
    ),
    TelemetryBlockCase(
        name="not_yet_valid_carries_every_license_field",
        status=LicenseStatus(state=LicenseState.NOT_YET_VALID, license=LICENSE, days_remaining=400),
        expected={"state": "not_yet_valid", **LICENSE_BLOCK_FIELDS},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TELEMETRY_BLOCK_CASES])
def test_license_block_reports_the_license_fields_of_the_state(test_case: TelemetryBlockCase) -> None:
    block = license_block(status=test_case.status)

    assert (block.model_dump(mode="json") if block is not None else None) == test_case.expected


@pytest.mark.parametrize(
    "test_case", [pytest.param(tc, id=tc.name) for tc in TELEMETRY_BLOCK_CASES if tc.expected is not None]
)
def test_license_block_never_carries_the_customer_name(test_case: TelemetryBlockCase) -> None:
    block = license_block(status=test_case.status)

    assert block is not None
    assert "Example Networks" not in json.dumps(block.model_dump(mode="json"))


REPORT_LICENSE = replace(
    LICENSE,
    customer_name="ACME Test Ltd",
    starts_at=datetime(2026, 10, 1, tzinfo=UTC),
    ends_at=datetime(2027, 10, 1, tzinfo=UTC),
)
FUTURE_LICENSE = replace(
    REPORT_LICENSE, starts_at=datetime(2027, 10, 1, tzinfo=UTC), ends_at=datetime(2028, 10, 1, tzinfo=UTC)
)
UNLICENSED_ADVICE = "  Set INFRAHUB_LICENSE_KEY on the servers and task workers."
EXPIRED_LINE = "License: expired on 2027-09-30, 4 days ago. Renew it and set the new INFRAHUB_LICENSE_KEY."
NOT_YET_VALID_LINE = "License: starts on 2027-10-01. Infrahub runs as unlicensed until then."
BAD_SIGNATURE_LINE = (
    "License: could not be verified (bad_signature). Check INFRAHUB_LICENSE_KEY on the servers and task workers."
)
INTERNAL_ERROR_LINE = "License: could not be determined because of an internal error. Check the server logs."


@dataclass
class ReportLinesCase:
    name: str
    status: LicenseStatus
    notice_mode: NoticeMode
    enforcing_release: str | None
    expected: list[str]


REPORT_LINES_CASES: list[ReportLinesCase] = [
    ReportLinesCase(
        name="not_required_prints_nothing",
        status=LicenseStatus(state=LicenseState.NOT_REQUIRED),
        notice_mode=NoticeMode.QUIET,
        enforcing_release="1.13",
        expected=[],
    ),
    ReportLinesCase(
        name="unlicensed_in_quiet_mode_names_the_enforcing_release",
        status=LicenseStatus(state=LicenseState.UNLICENSED),
        notice_mode=NoticeMode.QUIET,
        enforcing_release="1.13",
        expected=[
            "License: not set",
            UNLICENSED_ADVICE,
            "  From Infrahub 1.13, every user sees an Unlicensed banner without it.",
        ],
    ),
    ReportLinesCase(
        name="unlicensed_in_quiet_mode_without_an_enforcing_release_names_a_future_release",
        status=LicenseStatus(state=LicenseState.UNLICENSED),
        notice_mode=NoticeMode.QUIET,
        enforcing_release=None,
        expected=[
            "License: not set",
            UNLICENSED_ADVICE,
            "  In a future release, every user will see an Unlicensed banner without it.",
        ],
    ),
    ReportLinesCase(
        name="unlicensed_in_enforce_mode_says_every_user_sees_the_banner",
        status=LicenseStatus(state=LicenseState.UNLICENSED),
        notice_mode=NoticeMode.ENFORCE,
        enforcing_release="1.13",
        expected=[
            "License: not set",
            "  Every user sees an Unlicensed banner until INFRAHUB_LICENSE_KEY is set on the servers and task workers.",
        ],
    ),
    ReportLinesCase(
        name="valid_names_the_customer_the_type_and_the_last_covered_day",
        status=LicenseStatus(state=LicenseState.VALID, license=REPORT_LICENSE, days_remaining=200),
        notice_mode=NoticeMode.QUIET,
        enforcing_release="1.13",
        expected=["License: ACME Test Ltd, commercial, ends 2027-09-30"],
    ),
    ReportLinesCase(
        name="valid_evaluation_license_reads_evaluation",
        status=LicenseStatus(
            state=LicenseState.VALID, license=replace(REPORT_LICENSE, license_type="evaluation"), days_remaining=200
        ),
        notice_mode=NoticeMode.QUIET,
        enforcing_release="1.13",
        expected=["License: ACME Test Ltd, evaluation, ends 2027-09-30"],
    ),
    ReportLinesCase(
        name="valid_license_of_an_unknown_type_reads_commercial",
        status=LicenseStatus(
            state=LicenseState.VALID, license=replace(REPORT_LICENSE, license_type="partner"), days_remaining=200
        ),
        notice_mode=NoticeMode.QUIET,
        enforcing_release="1.13",
        expected=["License: ACME Test Ltd, commercial, ends 2027-09-30"],
    ),
    ReportLinesCase(
        name="expiring_in_quiet_mode_has_no_release_note",
        status=LicenseStatus(state=LicenseState.EXPIRING, license=REPORT_LICENSE, days_remaining=12),
        notice_mode=NoticeMode.QUIET,
        enforcing_release="1.13",
        expected=["License: ACME Test Ltd, commercial, expires in 12 days (2027-09-30)"],
    ),
    ReportLinesCase(
        name="expiring_in_enforce_mode",
        status=LicenseStatus(state=LicenseState.EXPIRING, license=REPORT_LICENSE, days_remaining=12),
        notice_mode=NoticeMode.ENFORCE,
        enforcing_release="1.13",
        expected=["License: ACME Test Ltd, commercial, expires in 12 days (2027-09-30)"],
    ),
    ReportLinesCase(
        name="expiring_in_one_day_reads_one_day",
        status=LicenseStatus(state=LicenseState.EXPIRING, license=REPORT_LICENSE, days_remaining=1),
        notice_mode=NoticeMode.ENFORCE,
        enforcing_release="1.13",
        expected=["License: ACME Test Ltd, commercial, expires in 1 day (2027-09-30)"],
    ),
    ReportLinesCase(
        name="expired_in_quiet_mode_names_the_enforcing_release",
        status=LicenseStatus(state=LicenseState.EXPIRED, license=REPORT_LICENSE, days_since_expiry=4),
        notice_mode=NoticeMode.QUIET,
        enforcing_release="1.13",
        expected=[EXPIRED_LINE, "  From Infrahub 1.13, every user sees a license banner until this is resolved."],
    ),
    ReportLinesCase(
        name="expired_in_enforce_mode",
        status=LicenseStatus(state=LicenseState.EXPIRED, license=REPORT_LICENSE, days_since_expiry=4),
        notice_mode=NoticeMode.ENFORCE,
        enforcing_release="1.13",
        expected=[EXPIRED_LINE],
    ),
    ReportLinesCase(
        name="expired_less_than_a_day_ago_reads_today",
        status=LicenseStatus(state=LicenseState.EXPIRED, license=REPORT_LICENSE, days_since_expiry=0),
        notice_mode=NoticeMode.ENFORCE,
        enforcing_release="1.13",
        expected=["License: expired on 2027-09-30, today. Renew it and set the new INFRAHUB_LICENSE_KEY."],
    ),
    ReportLinesCase(
        name="expired_one_day_ago_reads_one_day",
        status=LicenseStatus(state=LicenseState.EXPIRED, license=REPORT_LICENSE, days_since_expiry=1),
        notice_mode=NoticeMode.ENFORCE,
        enforcing_release="1.13",
        expected=["License: expired on 2027-09-30, 1 day ago. Renew it and set the new INFRAHUB_LICENSE_KEY."],
    ),
    ReportLinesCase(
        name="not_yet_valid_in_quiet_mode_without_an_enforcing_release_names_a_future_release",
        status=LicenseStatus(state=LicenseState.NOT_YET_VALID, license=FUTURE_LICENSE, days_remaining=400),
        notice_mode=NoticeMode.QUIET,
        enforcing_release=None,
        expected=[
            NOT_YET_VALID_LINE,
            "  In a future release, every user will see a license banner until this is resolved.",
        ],
    ),
    ReportLinesCase(
        name="not_yet_valid_in_enforce_mode",
        status=LicenseStatus(state=LicenseState.NOT_YET_VALID, license=FUTURE_LICENSE, days_remaining=400),
        notice_mode=NoticeMode.ENFORCE,
        enforcing_release="1.13",
        expected=[NOT_YET_VALID_LINE],
    ),
    ReportLinesCase(
        name="invalid_in_quiet_mode_names_the_reason_and_the_enforcing_release",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.BAD_SIGNATURE),
        notice_mode=NoticeMode.QUIET,
        enforcing_release="1.13",
        expected=[BAD_SIGNATURE_LINE, "  From Infrahub 1.13, every user sees a license banner until this is resolved."],
    ),
    ReportLinesCase(
        name="invalid_in_enforce_mode_names_the_reason",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.BAD_SIGNATURE),
        notice_mode=NoticeMode.ENFORCE,
        enforcing_release="1.13",
        expected=[BAD_SIGNATURE_LINE],
    ),
    ReportLinesCase(
        name="invalid_from_an_internal_error_in_quiet_mode_points_at_the_logs_without_a_release_note",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.INTERNAL_ERROR),
        notice_mode=NoticeMode.QUIET,
        enforcing_release="1.13",
        expected=[INTERNAL_ERROR_LINE],
    ),
    ReportLinesCase(
        name="invalid_from_an_internal_error_in_enforce_mode_points_at_the_logs",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.INTERNAL_ERROR),
        notice_mode=NoticeMode.ENFORCE,
        enforcing_release="1.13",
        expected=[INTERNAL_ERROR_LINE],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REPORT_LINES_CASES])
def test_license_report_lines_describe_the_state_and_what_to_set(test_case: ReportLinesCase) -> None:
    lines = license_report_lines(
        status=test_case.status, notice_mode=test_case.notice_mode, enforcing_release=test_case.enforcing_release
    )

    assert lines == test_case.expected


@dataclass
class ReportDateCase:
    name: str
    status: LicenseStatus
    expected: list[str]


REPORT_DATE_CASES: list[ReportDateCase] = [
    ReportDateCase(
        name="end_during_a_day_shows_that_day",
        status=LicenseStatus(
            state=LicenseState.VALID,
            license=replace(REPORT_LICENSE, ends_at=datetime(2027, 9, 30, 12, tzinfo=UTC)),
            days_remaining=200,
        ),
        expected=["License: ACME Test Ltd, commercial, ends 2027-09-30"],
    ),
    ReportDateCase(
        name="end_less_than_a_second_after_midnight_shows_that_day",
        status=LicenseStatus(
            state=LicenseState.VALID,
            license=replace(REPORT_LICENSE, ends_at=datetime(2027, 9, 30, 0, 0, 0, 500000, tzinfo=UTC)),
            days_remaining=200,
        ),
        expected=["License: ACME Test Ltd, commercial, ends 2027-09-30"],
    ),
    ReportDateCase(
        name="end_given_in_another_timezone_shows_the_utc_day",
        status=LicenseStatus(
            state=LicenseState.EXPIRING,
            license=replace(REPORT_LICENSE, ends_at=datetime(2027, 10, 1, 1, tzinfo=timezone(timedelta(hours=2)))),
            days_remaining=12,
        ),
        expected=["License: ACME Test Ltd, commercial, expires in 12 days (2027-09-30)"],
    ),
    ReportDateCase(
        name="start_given_in_another_timezone_shows_the_utc_day",
        status=LicenseStatus(
            state=LicenseState.NOT_YET_VALID,
            license=replace(FUTURE_LICENSE, starts_at=datetime(2027, 10, 1, 1, tzinfo=timezone(timedelta(hours=2)))),
            days_remaining=400,
        ),
        expected=["License: starts on 2027-09-30. Infrahub runs as unlicensed until then."],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REPORT_DATE_CASES])
def test_license_report_lines_show_dates_as_utc_days(test_case: ReportDateCase) -> None:
    """The end shown is the last day the license covers, one microsecond before its end instant."""
    lines = license_report_lines(status=test_case.status, notice_mode=NoticeMode.ENFORCE, enforcing_release=None)

    assert lines == test_case.expected
