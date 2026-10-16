from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import FastAPI, Request

from infrahub.api import internal
from infrahub.api.internal import get_info
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.license.models import License, LicenseFailureReason, LicenseState, LicenseStatus, NoticeMode
from infrahub.license.service import LicenseService, LicenseServiceCommunity
from infrahub.workers.dependencies import build_license_service
from tests.adapters.license import (
    FailingLicenseService,
    FailingNoticeModeLicenseService,
    RecordingLicenseService,
    build_license,
)
from tests.helpers.dependency_override import override_dependency
from tests.helpers.log import find_logged_events

if TYPE_CHECKING:
    from fast_depends import Provider

SESSION = AccountSession(account_id="account-1", auth_type=AuthType.JWT)
ANONYMOUS = AccountSession(authenticated=False, account_id="anonymous", auth_type=AuthType.NONE)

COMMERCIAL = License(
    license_id="f67dea44-7d3b-4c1e-9a52-1b0f3c2d4e5f",
    customer_name="ACME Test Ltd",
    license_type="commercial",
    product_tier="medium",
    support_tier="advanced",
    starts_at=datetime(2026, 9, 30, tzinfo=UTC),
    ends_at=datetime(2027, 9, 30, tzinfo=UTC),
    issued_at=datetime(2026, 9, 29, tzinfo=UTC),
    issuer="opsmill-test",
)
EVALUATION = License(
    license_id="0b6c1f7e-2a4d-4e8b-8c3f-5d9e7a1b2c3d",
    customer_name="ACME Trial Ltd",
    license_type="evaluation",
    product_tier="small",
    support_tier="standard",
    starts_at=datetime(2026, 9, 1, tzinfo=UTC),
    ends_at=datetime(2027, 3, 1, tzinfo=UTC),
    issued_at=datetime(2026, 8, 31, tzinfo=UTC),
    issuer="opsmill-test",
)
NO_LICENSE_DETAILS: dict[str, Any] = {
    "license_id": None,
    "license_type": None,
    "customer_name": None,
    "product_tier": None,
    "support_tier": None,
    "starts_at": None,
    "ends_at": None,
}
COMMERCIAL_DETAILS: dict[str, Any] = {
    "license_id": "f67dea44-7d3b-4c1e-9a52-1b0f3c2d4e5f",
    "license_type": "commercial",
    "customer_name": "ACME Test Ltd",
    "product_tier": "medium",
    "support_tier": "advanced",
    "starts_at": "2026-09-30T00:00:00Z",
    "ends_at": "2027-09-30T00:00:00Z",
}


def _request() -> Request:
    return Request(scope={"type": "http", "app": FastAPI(version="1.12.0")})


@dataclass
class LicenseObjectCase:
    name: str
    service: LicenseService
    expected: dict[str, Any]
    """The whole license object as serialized in the response, so any extra or missing field fails."""


LICENSE_OBJECT_CASES: list[LicenseObjectCase] = [
    LicenseObjectCase(
        name="not_required",
        service=LicenseServiceCommunity(),
        expected={
            "state": "not_required",
            "reason": None,
            **NO_LICENSE_DETAILS,
            "days_remaining": None,
            "days_since_expiry": None,
            "notice_mode": "quiet",
            "enforcing_release": None,
            "banner": {"audience": "none", "dismissible": False, "shown_to_all_users_when_enforced": False},
        },
    ),
    LicenseObjectCase(
        name="unlicensed_in_enforce_mode",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.UNLICENSED), notice_mode=NoticeMode.ENFORCE
        ),
        expected={
            "state": "unlicensed",
            "reason": None,
            **NO_LICENSE_DETAILS,
            "days_remaining": None,
            "days_since_expiry": None,
            "notice_mode": "enforce",
            "enforcing_release": None,
            "banner": {"audience": "all_users", "dismissible": False, "shown_to_all_users_when_enforced": False},
        },
    ),
    LicenseObjectCase(
        name="unlicensed_in_quiet_mode",
        service=RecordingLicenseService(status=LicenseStatus(state=LicenseState.UNLICENSED), enforcing_release="1.13"),
        expected={
            "state": "unlicensed",
            "reason": None,
            **NO_LICENSE_DETAILS,
            "days_remaining": None,
            "days_since_expiry": None,
            "notice_mode": "quiet",
            "enforcing_release": "1.13",
            "banner": {"audience": "super_admins", "dismissible": True, "shown_to_all_users_when_enforced": True},
        },
    ),
    LicenseObjectCase(
        name="invalid_carries_the_reason_and_no_details",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.BAD_SIGNATURE),
            enforcing_release="1.13",
        ),
        expected={
            "state": "invalid",
            "reason": "bad_signature",
            **NO_LICENSE_DETAILS,
            "days_remaining": None,
            "days_since_expiry": None,
            "notice_mode": "quiet",
            "enforcing_release": "1.13",
            "banner": {"audience": "super_admins", "dismissible": True, "shown_to_all_users_when_enforced": True},
        },
    ),
    LicenseObjectCase(
        name="expiring",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.EXPIRING, license=COMMERCIAL, days_remaining=12)
        ),
        expected={
            "state": "expiring",
            "reason": None,
            **COMMERCIAL_DETAILS,
            "days_remaining": 12,
            "days_since_expiry": None,
            "notice_mode": "quiet",
            "enforcing_release": None,
            "banner": {"audience": "super_admins", "dismissible": True, "shown_to_all_users_when_enforced": False},
        },
    ),
    LicenseObjectCase(
        name="expired_in_quiet_mode",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.EXPIRED, license=COMMERCIAL, days_since_expiry=4)
        ),
        expected={
            "state": "expired",
            "reason": None,
            **COMMERCIAL_DETAILS,
            "days_remaining": None,
            "days_since_expiry": 4,
            "notice_mode": "quiet",
            "enforcing_release": None,
            "banner": {"audience": "super_admins", "dismissible": True, "shown_to_all_users_when_enforced": True},
        },
    ),
    LicenseObjectCase(
        name="expired_in_enforce_mode",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.EXPIRED, license=COMMERCIAL, days_since_expiry=4),
            notice_mode=NoticeMode.ENFORCE,
            enforcing_release="1.13",
        ),
        expected={
            "state": "expired",
            "reason": None,
            **COMMERCIAL_DETAILS,
            "days_remaining": None,
            "days_since_expiry": 4,
            "notice_mode": "enforce",
            "enforcing_release": "1.13",
            "banner": {"audience": "all_users", "dismissible": False, "shown_to_all_users_when_enforced": False},
        },
    ),
    LicenseObjectCase(
        name="valid_evaluation",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.VALID, license=EVALUATION, days_remaining=150),
            notice_mode=NoticeMode.ENFORCE,
            enforcing_release="1.13",
        ),
        expected={
            "state": "valid",
            "reason": None,
            "license_id": "0b6c1f7e-2a4d-4e8b-8c3f-5d9e7a1b2c3d",
            "license_type": "evaluation",
            "customer_name": "ACME Trial Ltd",
            "product_tier": "small",
            "support_tier": "standard",
            "starts_at": "2026-09-01T00:00:00Z",
            "ends_at": "2027-03-01T00:00:00Z",
            "days_remaining": 150,
            "days_since_expiry": None,
            "notice_mode": "enforce",
            "enforcing_release": "1.13",
            "banner": {"audience": "none", "dismissible": False, "shown_to_all_users_when_enforced": False},
        },
    ),
    LicenseObjectCase(
        name="failing_service_reports_an_internal_error",
        service=FailingLicenseService(),
        expected={
            "state": "invalid",
            "reason": "internal_error",
            **NO_LICENSE_DETAILS,
            "days_remaining": None,
            "days_since_expiry": None,
            "notice_mode": "quiet",
            "enforcing_release": None,
            "banner": {"audience": "super_admins", "dismissible": True, "shown_to_all_users_when_enforced": False},
        },
    ),
    LicenseObjectCase(
        name="failing_service_in_enforce_mode_stays_with_super_admins",
        service=FailingLicenseService(notice_mode=NoticeMode.ENFORCE, enforcing_release="1.13"),
        expected={
            "state": "invalid",
            "reason": "internal_error",
            **NO_LICENSE_DETAILS,
            "days_remaining": None,
            "days_since_expiry": None,
            "notice_mode": "enforce",
            "enforcing_release": "1.13",
            "banner": {"audience": "super_admins", "dismissible": True, "shown_to_all_users_when_enforced": False},
        },
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in LICENSE_OBJECT_CASES])
async def test_info_reports_the_license_object(case: LicenseObjectCase, dependency_provider: Provider) -> None:
    with override_dependency(
        original=build_license_service, override=lambda: case.service, dependency_provider=dependency_provider
    ):
        info = await get_info(request=_request(), account_session=SESSION)

    assert info.model_dump(mode="json")["license"] == case.expected


async def test_info_carries_no_license_object_for_anonymous_callers(dependency_provider: Provider) -> None:
    """Whether and to whom the deployment is licensed is for signed-in users only."""
    service = RecordingLicenseService(
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.BAD_SIGNATURE)
    )

    with override_dependency(
        original=build_license_service, override=lambda: service, dependency_provider=dependency_provider
    ):
        info = await get_info(request=_request(), account_session=ANONYMOUS)

    assert info.license is None


INTERNAL_ERROR_OBJECT: dict[str, Any] = {
    "state": "invalid",
    "reason": "internal_error",
    **NO_LICENSE_DETAILS,
    "days_remaining": None,
    "days_since_expiry": None,
    "notice_mode": "quiet",
    "enforcing_release": None,
    "banner": {"audience": "super_admins", "dismissible": True, "shown_to_all_users_when_enforced": False},
}


def _license_with_a_number_as_its_product_tier() -> License:
    granted = build_license()
    # The constructor rejects a number in a text field, so the defect is planted after construction.
    vars(granted)["product_tier"] = 3
    return granted


@pytest.fixture
def license_object_failure_not_logged_yet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(internal, "_license_object_failure", internal._FailureLog())


@pytest.mark.parametrize(
    "service",
    [
        pytest.param(
            FailingNoticeModeLicenseService(status=LicenseStatus(state=LicenseState.UNLICENSED)),
            id="notice_mode_raises",
        ),
        pytest.param(
            RecordingLicenseService(
                status=LicenseStatus(
                    state=LicenseState.VALID, license=_license_with_a_number_as_its_product_tier(), days_remaining=150
                )
            ),
            id="license_object_rejects_the_status",
        ),
    ],
)
@pytest.mark.usefixtures("license_object_failure_not_logged_yet")
async def test_info_reports_an_internal_error_when_the_license_object_cannot_be_built(
    service: LicenseService, dependency_provider: Provider, caplog: pytest.LogCaptureFixture
) -> None:
    """The traceback is logged on the first failure only, since every later request fails the same way."""
    with (
        caplog.at_level("ERROR", logger="infrahub"),
        override_dependency(
            original=build_license_service, override=lambda: service, dependency_provider=dependency_provider
        ),
    ):
        first = await get_info(request=_request(), account_session=SESSION)
        second = await get_info(request=_request(), account_session=SESSION)

    assert first.model_dump(mode="json")["license"] == INTERNAL_ERROR_OBJECT
    assert second.model_dump(mode="json")["license"] == INTERNAL_ERROR_OBJECT
    failures = find_logged_events(
        caplog,
        event="The license object could not be built; reporting the license as invalid with reason internal_error",
    )
    assert len(failures) == 1
    assert failures[0]["level"] == "error"
    assert failures[0]["exc_info"] is True
