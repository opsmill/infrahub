from __future__ import annotations

from datetime import UTC, datetime

import pytest

from infrahub.license.models import LicenseFailureReason, LicenseState, LicenseStatus, NoticeMode
from infrahub.license.service import LicenseServiceCommunity, LicenseServiceUnavailable, read_license_status
from tests.adapters.license import FailingLicenseService, RecordingLicenseService
from tests.helpers.log import find_logged_events

NOW = datetime(2026, 6, 1, tzinfo=UTC)


@pytest.mark.parametrize("now", [None, NOW], ids=["current_time", "fixed_time"])
def test_community_service_reports_no_license_required(now: datetime | None) -> None:
    assert LicenseServiceCommunity().status(now=now) == LicenseStatus(state=LicenseState.NOT_REQUIRED)


def test_community_service_shows_notices_to_super_admins_only_with_no_enforcing_release() -> None:
    service = LicenseServiceCommunity()

    assert service.notice_mode is NoticeMode.QUIET
    assert service.enforcing_release is None


def test_unavailable_service_reports_an_internal_error_to_super_admins_only() -> None:
    service = LicenseServiceUnavailable()

    assert service.status(now=NOW) == LicenseStatus(
        state=LicenseState.INVALID, reason=LicenseFailureReason.INTERNAL_ERROR
    )
    assert service.notice_mode is NoticeMode.QUIET
    assert service.enforcing_release is None


def test_read_license_status_returns_the_service_status_for_the_given_time() -> None:
    expected = LicenseStatus(state=LicenseState.UNLICENSED)
    service = RecordingLicenseService(status=expected)

    assert read_license_status(service=service, now=NOW) == expected
    assert service.requested_at == [NOW]


def test_read_license_status_reports_a_failing_service_as_invalid_and_logs_the_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("ERROR", logger="infrahub"):
        status = read_license_status(service=FailingLicenseService(), now=NOW)

    assert status == LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.INTERNAL_ERROR)
    failures = find_logged_events(
        caplog, event="The license service failed; reporting the license as invalid with reason internal_error"
    )
    assert len(failures) == 1
    assert failures[0]["level"] == "error"
    assert failures[0]["exc_info"] is True
