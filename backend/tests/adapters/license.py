from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from infrahub.license.models import (
    License,
    LicenseFailure,
    LicenseFailureReason,
    LicenseState,
    LicenseStatus,
    NoticeMode,
)
from infrahub.license.service import LicenseService, LicenseServiceCommunity
from infrahub.license.status import evaluate

_INSTANT_IN_STATE: dict[LicenseState, datetime] = {
    LicenseState.NOT_YET_VALID: datetime(2025, 12, 1, tzinfo=UTC),
    LicenseState.VALID: datetime(2026, 6, 1, tzinfo=UTC),
    LicenseState.EXPIRING: datetime(2026, 12, 20, tzinfo=UTC),
    LicenseState.EXPIRED: datetime(2027, 1, 5, tzinfo=UTC),
}


def build_license(**overrides: Any) -> License:
    """Build a commercial license valid from 2026-01-01 to 2027-01-01 UTC, with any field overridden."""
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


def build_license_status(
    state: LicenseState, reason: LicenseFailureReason = LicenseFailureReason.BAD_SIGNATURE
) -> LicenseStatus:
    """Build a complete status in ``state`` from the default license; ``reason`` is used only for invalid."""
    if state == LicenseState.NOT_REQUIRED:
        status = LicenseServiceCommunity().status()
    elif state == LicenseState.UNLICENSED:
        status = evaluate(outcome=None, now=_INSTANT_IN_STATE[LicenseState.VALID])
    elif state == LicenseState.INVALID:
        status = evaluate(outcome=LicenseFailure(reason=reason), now=_INSTANT_IN_STATE[LicenseState.VALID])
    else:
        status = evaluate(outcome=build_license(), now=_INSTANT_IN_STATE[state])
    assert status.state is state, f"built a '{status.state}' status when '{state}' was requested"
    return status


class RecordingLicenseService(LicenseService):
    """Reports a fixed license status and records the instant passed to each read."""

    def __init__(
        self,
        status: LicenseStatus,
        notice_mode: NoticeMode = NoticeMode.QUIET,
        enforcing_release: str | None = None,
    ) -> None:
        self._status = status
        self._notice_mode = notice_mode
        self._enforcing_release = enforcing_release
        self.requested_at: list[datetime | None] = []

    @property
    def notice_mode(self) -> NoticeMode:
        return self._notice_mode

    @property
    def enforcing_release(self) -> str | None:
        return self._enforcing_release

    def status(self, now: datetime | None = None) -> LicenseStatus:
        self.requested_at.append(now)
        return self._status


class FailingLicenseService(LicenseService):
    """Raises on every status read, as a defective license service would."""

    def __init__(
        self,
        notice_mode: NoticeMode = NoticeMode.QUIET,
        enforcing_release: str | None = None,
        error_type: type[Exception] = RuntimeError,
    ) -> None:
        self._notice_mode = notice_mode
        self._enforcing_release = enforcing_release
        self._error_type = error_type

    @property
    def notice_mode(self) -> NoticeMode:
        return self._notice_mode

    @property
    def enforcing_release(self) -> str | None:
        return self._enforcing_release

    def status(self, now: datetime | None = None) -> LicenseStatus:
        raise self._error_type(f"license service failure at {now}")


class FailingNoticeModeLicenseService(LicenseService):
    """Reports a fixed license status but raises on reading the notice mode, which a service must never do."""

    def __init__(self, status: LicenseStatus) -> None:
        self._status = status

    @property
    def notice_mode(self) -> NoticeMode:
        raise RuntimeError("license notice mode failure")

    @property
    def enforcing_release(self) -> str | None:
        return None

    def status(self, now: datetime | None = None) -> LicenseStatus:
        return self._status
