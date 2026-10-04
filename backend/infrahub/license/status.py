from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import assert_never

from infrahub.license.models import (
    License,
    LicenseFailure,
    LicenseFailureReason,
    LicenseState,
    LicenseStatus,
    Notice,
    NoticeAudience,
    NoticeMode,
)

EXPIRING_WINDOW = timedelta(days=30)
_ONE_DAY = timedelta(days=1)


def _state_of(granted: License, now: datetime) -> LicenseState:
    if now < granted.starts_at:
        return LicenseState.NOT_YET_VALID
    if now >= granted.ends_at:
        return LicenseState.EXPIRED
    if now >= granted.ends_at - EXPIRING_WINDOW:
        return LicenseState.EXPIRING
    return LicenseState.VALID


def evaluate(outcome: License | LicenseFailure | None, now: datetime) -> LicenseStatus:
    """Derive the license state at ``now`` from a verification outcome, where ``None`` means no license was supplied."""
    if outcome is None:
        return LicenseStatus(state=LicenseState.UNLICENSED)
    if isinstance(outcome, LicenseFailure):
        return LicenseStatus(state=LicenseState.INVALID, reason=outcome.reason)

    state = _state_of(granted=outcome, now=now)
    if now < outcome.ends_at:
        return LicenseStatus(state=state, license=outcome, days_remaining=math.ceil((outcome.ends_at - now) / _ONE_DAY))
    return LicenseStatus(state=state, license=outcome, days_since_expiry=(now - outcome.ends_at) // _ONE_DAY)


def notice_for(status: LicenseStatus, mode: NoticeMode) -> Notice:
    """Decide who sees a license notice, whether it can be dismissed and whether responses carry the header."""
    # An internal error is a defect in Infrahub rather than in the customer's license, so it never reaches every user.
    if status.state == LicenseState.INVALID and status.reason == LicenseFailureReason.INTERNAL_ERROR:
        return Notice(audience=NoticeAudience.SUPER_ADMINS, dismissible=True, send_header=False)

    match status.state:
        case LicenseState.NOT_REQUIRED | LicenseState.VALID:
            return Notice(audience=NoticeAudience.NONE, dismissible=False, send_header=False)
        case LicenseState.EXPIRING:
            return Notice(
                audience=NoticeAudience.SUPER_ADMINS, dismissible=True, send_header=mode == NoticeMode.ENFORCE
            )
        case LicenseState.UNLICENSED | LicenseState.INVALID | LicenseState.NOT_YET_VALID | LicenseState.EXPIRED:
            if mode == NoticeMode.QUIET:
                return Notice(audience=NoticeAudience.SUPER_ADMINS, dismissible=True, send_header=False)
            return Notice(audience=NoticeAudience.ALL_USERS, dismissible=False, send_header=True)
        case _:
            assert_never(status.state)


def shown_to_all_users_when_enforced(status: LicenseStatus, mode: NoticeMode) -> bool:
    """Whether a notice that only super-admins see in quiet mode reaches every user in the enforcing release."""
    return (
        mode == NoticeMode.QUIET
        and notice_for(status=status, mode=NoticeMode.ENFORCE).audience == NoticeAudience.ALL_USERS
    )
