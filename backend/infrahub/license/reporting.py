from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, assert_never

from infrahub.license.models import (
    License,
    LicenseFailureReason,
    LicenseState,
    LicenseStatus,
    LicenseType,
    NoticeAudience,
    NoticeMode,
)
from infrahub.license.service import read_license_status
from infrahub.license.status import notice_for, shown_to_all_users_when_enforced
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


_ONE_SECOND = timedelta(seconds=1)


def license_report_lines(status: LicenseStatus, notice_mode: NoticeMode, enforcing_release: str | None) -> list[str]:
    """Return the license section of the upgrade output, empty when no license is required.

    Raises:
        ValueError: When the status lacks the license details its state requires.

    """
    lines = _state_lines(status=status, notice_mode=notice_mode)
    if shown_to_all_users_when_enforced(status=status, mode=notice_mode):
        lines.append(_enforcing_release_note(state=status.state, enforcing_release=enforcing_release))
    return lines


def _state_lines(status: LicenseStatus, notice_mode: NoticeMode) -> list[str]:
    match status.state:
        case LicenseState.NOT_REQUIRED:
            return []
        case LicenseState.UNLICENSED if (
            notice_for(status=status, mode=notice_mode).audience == NoticeAudience.ALL_USERS
        ):
            return [
                "License: not set",
                "  Every user sees an Unlicensed banner until INFRAHUB_LICENSE_KEY is set on the servers and task workers.",
            ]
        case LicenseState.UNLICENSED:
            return ["License: not set", "  Set INFRAHUB_LICENSE_KEY on the servers and task workers."]
        case LicenseState.INVALID if status.reason == LicenseFailureReason.INTERNAL_ERROR:
            return ["License: could not be determined because of an internal error. Check the server logs."]
        case LicenseState.INVALID:
            reason = "" if status.reason is None else f" ({status.reason.value})"
            return [
                f"License: could not be verified{reason}. Check INFRAHUB_LICENSE_KEY on the servers and task workers."
            ]
        case LicenseState.VALID | LicenseState.EXPIRING | LicenseState.EXPIRED | LicenseState.NOT_YET_VALID:
            return [f"License: {_granted_summary(status=status)}"]
        case _:
            assert_never(status.state)


def _granted_summary(status: LicenseStatus) -> str:
    match status:
        case LicenseStatus(state=LicenseState.VALID, license=License() as granted):
            return f"{granted.customer_name}, {_type_of(granted)}, ends {_last_covered_day(granted)}"
        case LicenseStatus(state=LicenseState.EXPIRING, license=License() as granted, days_remaining=int() as days):
            return (
                f"{granted.customer_name}, {_type_of(granted)}, expires in {_day_count(days)} "
                f"({_last_covered_day(granted)})"
            )
        case LicenseStatus(state=LicenseState.EXPIRED, license=License() as granted, days_since_expiry=int() as days):
            since = "today" if days == 0 else f"{_day_count(days)} ago"
            return f"expired on {_last_covered_day(granted)}, {since}. Renew it and set the new INFRAHUB_LICENSE_KEY."
        case LicenseStatus(state=LicenseState.NOT_YET_VALID, license=License() as granted):
            return f"starts on {granted.starts_at.date().isoformat()}. Infrahub runs as unlicensed until then."
    raise ValueError(f"License status in state '{status.state.value}' lacks the license details that state requires")


def _type_of(granted: License) -> str:
    return LicenseType.EVALUATION.value if granted.is_evaluation else LicenseType.COMMERCIAL.value


def _last_covered_day(granted: License) -> str:
    return (granted.ends_at - _ONE_SECOND).date().isoformat()


def _day_count(days: int) -> str:
    return f"{days} day" if days == 1 else f"{days} days"


def _enforcing_release_note(state: LicenseState, enforcing_release: str | None) -> str:
    banner = (
        "an Unlicensed banner without it"
        if state == LicenseState.UNLICENSED
        else "a license banner until this is resolved"
    )
    if enforcing_release is None:
        return f"  In a future release, every user will see {banner}."
    return f"  From Infrahub {enforcing_release}, every user sees {banner}."
