from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from infrahub.license.models import LicenseFailure, LicenseFailureReason, LicenseState, LicenseStatus, NoticeMode
from infrahub.license.status import evaluate
from infrahub.log import get_logger

log = get_logger()


class LicenseService(ABC):
    """Source of the license state, replaced by an edition that requires a license."""

    @property
    @abstractmethod
    def notice_mode(self) -> NoticeMode:
        """Release-wide rule for license notices, constant for a given release."""

    @property
    @abstractmethod
    def enforcing_release(self) -> str | None:
        """Release in which every user starts seeing license problem notices, or None when not yet known."""

    @abstractmethod
    def status(self, now: datetime | None = None) -> LicenseStatus:
        """Return the license state at ``now``, defaulting to the current UTC time; never raises."""


class LicenseServiceCommunity(LicenseService):
    @property
    def notice_mode(self) -> NoticeMode:
        return NoticeMode.QUIET

    @property
    def enforcing_release(self) -> str | None:
        return None

    def status(self, now: datetime | None = None) -> LicenseStatus:  # noqa: ARG002
        return LicenseStatus(state=LicenseState.NOT_REQUIRED)


def read_license_status(service: LicenseService, now: datetime | None = None) -> LicenseStatus:
    """Return the service's license state, reporting any error it raises as invalid with an internal error."""
    try:
        return service.status(now=now)
    # Top-level boundary: a defect in a replaceable license service must not fail a startup or a request.
    except Exception:
        log.exception("The license service failed; reporting the license as invalid with reason internal_error")
        return evaluate(
            outcome=LicenseFailure(reason=LicenseFailureReason.INTERNAL_ERROR),
            now=now if now is not None else datetime.now(tz=UTC),
        )
