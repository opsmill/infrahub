from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.license.models import LicenseStatus, NoticeMode
from infrahub.license.service import LicenseService

if TYPE_CHECKING:
    from datetime import datetime


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
