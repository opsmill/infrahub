from __future__ import annotations

from typing import TYPE_CHECKING, Any, assert_never

from infrahub.license.models import LicenseFailureReason, LicenseState, LicenseStatus
from infrahub.license.service import read_license_status
from infrahub.log import get_logger
from infrahub.telemetry.models import TelemetryLicenseData

if TYPE_CHECKING:
    from infrahub.license.service import LicenseService

log = get_logger()


def _log_fields(status: LicenseStatus) -> dict[str, Any]:
    fields: dict[str, Any] = {"license_state": status.state.value}
    if status.reason is not None:
        fields["license_reason"] = status.reason.value
    if status.license is not None:
        fields["license_id"] = status.license.license_id
        fields["license_type"] = status.license.license_type
        fields["license_starts_at"] = status.license.starts_at.isoformat()
        fields["license_ends_at"] = status.license.ends_at.isoformat()
    if status.days_remaining is not None:
        fields["license_days_remaining"] = status.days_remaining
    if status.days_since_expiry is not None:
        fields["license_days_since_expiry"] = status.days_since_expiry
    return fields


def log_license_state(service: LicenseService, key_is_set: bool) -> None:
    """Log the license state once, at INFO, WARNING or ERROR by urgency; never raises, even when the service does."""
    status = read_license_status(service=service)
    fields = _log_fields(status=status)
    match status.state:
        case LicenseState.NOT_REQUIRED:
            if key_is_set:
                log.info(
                    "A license key is set but ignored, because this deployment does not require a license", **fields
                )
            else:
                log.info("No license is required for this deployment", **fields)
        case LicenseState.VALID:
            log.info("License is valid", **fields)
        case LicenseState.EXPIRING:
            log.warning(
                "License expires soon; set a renewed license in INFRAHUB_LICENSE_KEY on every API server and task worker",
                **fields,
            )
        case LicenseState.EXPIRED:
            log.warning(
                "License has expired; set a renewed license in INFRAHUB_LICENSE_KEY on every API server and task worker",
                **fields,
            )
        case LicenseState.NOT_YET_VALID:
            log.warning("License is not valid yet; check its start date and the server clock", **fields)
        case LicenseState.UNLICENSED:
            log.warning("No license is set; set INFRAHUB_LICENSE_KEY on every API server and task worker", **fields)
        case LicenseState.INVALID if status.reason == LicenseFailureReason.INTERNAL_ERROR:
            log.error(
                "License state could not be determined because of an internal error; see the error logged before",
                **fields,
            )
        case LicenseState.INVALID:
            log.error(
                "License could not be verified; check INFRAHUB_LICENSE_KEY on every API server and task worker",
                **fields,
            )
        case _:
            assert_never(status.state)


def license_block(status: LicenseStatus) -> TelemetryLicenseData | None:
    """Return the license block of the telemetry snapshot, ``None`` when no license is required; never the customer name."""
    match status.state:
        case LicenseState.NOT_REQUIRED:
            return None
        case LicenseState.UNLICENSED | LicenseState.INVALID:
            granted = None
        case LicenseState.VALID | LicenseState.EXPIRING | LicenseState.EXPIRED | LicenseState.NOT_YET_VALID:
            granted = status.license
        case _:
            assert_never(status.state)
    return TelemetryLicenseData(
        state=status.state.value,
        license_id=granted.license_id if granted else None,
        license_type=granted.license_type if granted else None,
        product_tier=granted.product_tier if granted else None,
        support_tier=granted.support_tier if granted else None,
        starts_at=granted.starts_at if granted else None,
        ends_at=granted.ends_at if granted else None,
        issuer=granted.issuer if granted else None,
    )
