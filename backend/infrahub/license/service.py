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


class LicenseServiceUnavailable(LicenseService):
    """Stands in for a license service that could not be built, reporting the license as invalid."""

    @property
    def notice_mode(self) -> NoticeMode:
        # A service that fails to build is a defect in the edition, not the customer's license, so only super-admins see it.
        return NoticeMode.QUIET

    @property
    def enforcing_release(self) -> str | None:
        return None

    def status(self, now: datetime | None = None) -> LicenseStatus:
        return evaluate(
            outcome=LicenseFailure(reason=LicenseFailureReason.INTERNAL_ERROR),
            now=now if now is not None else datetime.now(tz=UTC),
        )


# A service that keeps failing would otherwise log the same traceback on every request.
_reported_failure_types: set[type[Exception]] = set()


def read_license_status(service: LicenseService, now: datetime | None = None) -> LicenseStatus:
    """Return the service's license state, reporting an error it raises as invalid, logged once per exception type."""
    try:
        return service.status(now=now)
    # Top-level boundary: a defect in a replaceable license service must not fail a startup or a request.
    except Exception as exc:
        if type(exc) not in _reported_failure_types:
            _reported_failure_types.add(type(exc))
            log.exception("The license service failed; reporting the license as invalid with reason internal_error")
        return LicenseServiceUnavailable().status(now=now)
