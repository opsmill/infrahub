from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.license.models import (
    LicenseFailureReason,
    LicenseState,
    LicenseStatus,
    Notice,
    NoticeAudience,
    NoticeMode,
)
from infrahub.license.status import notice_for, shown_to_all_users_when_enforced

NO_NOTICE = Notice(audience=NoticeAudience.NONE, dismissible=False, send_header=False)
SUPER_ADMINS_DISMISSIBLE = Notice(audience=NoticeAudience.SUPER_ADMINS, dismissible=True, send_header=False)
SUPER_ADMINS_DISMISSIBLE_WITH_HEADER = Notice(audience=NoticeAudience.SUPER_ADMINS, dismissible=True, send_header=True)
ALL_USERS_PERSISTENT_WITH_HEADER = Notice(audience=NoticeAudience.ALL_USERS, dismissible=False, send_header=True)


@dataclass
class NoticeTestCase:
    name: str
    state: LicenseState
    mode: NoticeMode
    expected: Notice
    reason: LicenseFailureReason | None = None


NOTICE_TEST_CASES: list[NoticeTestCase] = [
    NoticeTestCase(
        name="not_required_quiet",
        state=LicenseState.NOT_REQUIRED,
        mode=NoticeMode.QUIET,
        expected=NO_NOTICE,
    ),
    NoticeTestCase(
        name="not_required_enforce",
        state=LicenseState.NOT_REQUIRED,
        mode=NoticeMode.ENFORCE,
        expected=NO_NOTICE,
    ),
    NoticeTestCase(
        name="valid_quiet",
        state=LicenseState.VALID,
        mode=NoticeMode.QUIET,
        expected=NO_NOTICE,
    ),
    NoticeTestCase(
        name="valid_enforce",
        state=LicenseState.VALID,
        mode=NoticeMode.ENFORCE,
        expected=NO_NOTICE,
    ),
    NoticeTestCase(
        name="expiring_quiet",
        state=LicenseState.EXPIRING,
        mode=NoticeMode.QUIET,
        expected=SUPER_ADMINS_DISMISSIBLE,
    ),
    NoticeTestCase(
        name="expiring_enforce",
        state=LicenseState.EXPIRING,
        mode=NoticeMode.ENFORCE,
        expected=SUPER_ADMINS_DISMISSIBLE_WITH_HEADER,
    ),
    NoticeTestCase(
        name="unlicensed_quiet",
        state=LicenseState.UNLICENSED,
        mode=NoticeMode.QUIET,
        expected=SUPER_ADMINS_DISMISSIBLE,
    ),
    NoticeTestCase(
        name="unlicensed_enforce",
        state=LicenseState.UNLICENSED,
        mode=NoticeMode.ENFORCE,
        expected=ALL_USERS_PERSISTENT_WITH_HEADER,
    ),
    NoticeTestCase(
        name="invalid_quiet",
        state=LicenseState.INVALID,
        mode=NoticeMode.QUIET,
        expected=SUPER_ADMINS_DISMISSIBLE,
    ),
    NoticeTestCase(
        name="invalid_enforce",
        state=LicenseState.INVALID,
        mode=NoticeMode.ENFORCE,
        expected=ALL_USERS_PERSISTENT_WITH_HEADER,
    ),
    NoticeTestCase(
        name="invalid_internal_error_quiet",
        state=LicenseState.INVALID,
        mode=NoticeMode.QUIET,
        expected=SUPER_ADMINS_DISMISSIBLE,
        reason=LicenseFailureReason.INTERNAL_ERROR,
    ),
    NoticeTestCase(
        name="invalid_internal_error_enforce",
        state=LicenseState.INVALID,
        mode=NoticeMode.ENFORCE,
        expected=SUPER_ADMINS_DISMISSIBLE,
        reason=LicenseFailureReason.INTERNAL_ERROR,
    ),
    NoticeTestCase(
        name="not_yet_valid_quiet",
        state=LicenseState.NOT_YET_VALID,
        mode=NoticeMode.QUIET,
        expected=SUPER_ADMINS_DISMISSIBLE,
    ),
    NoticeTestCase(
        name="not_yet_valid_enforce",
        state=LicenseState.NOT_YET_VALID,
        mode=NoticeMode.ENFORCE,
        expected=ALL_USERS_PERSISTENT_WITH_HEADER,
    ),
    NoticeTestCase(
        name="expired_quiet",
        state=LicenseState.EXPIRED,
        mode=NoticeMode.QUIET,
        expected=SUPER_ADMINS_DISMISSIBLE,
    ),
    NoticeTestCase(
        name="expired_enforce",
        state=LicenseState.EXPIRED,
        mode=NoticeMode.ENFORCE,
        expected=ALL_USERS_PERSISTENT_WITH_HEADER,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in NOTICE_TEST_CASES])
def test_notice_for_each_state_and_mode(test_case: NoticeTestCase) -> None:
    status = LicenseStatus(state=test_case.state, reason=test_case.reason)

    assert notice_for(status=status, mode=test_case.mode) == test_case.expected


def test_every_state_and_mode_is_covered() -> None:
    """Adding a state or a mode must come with its expected notice."""
    covered = {(test_case.state, test_case.mode) for test_case in NOTICE_TEST_CASES}

    assert covered == {(state, mode) for state in LicenseState for mode in NoticeMode}


@dataclass
class EnforcedAudienceTestCase:
    name: str
    status: LicenseStatus
    mode: NoticeMode
    expected: bool


ENFORCED_AUDIENCE_TEST_CASES: list[EnforcedAudienceTestCase] = [
    EnforcedAudienceTestCase(
        name="unlicensed_quiet",
        status=LicenseStatus(state=LicenseState.UNLICENSED),
        mode=NoticeMode.QUIET,
        expected=True,
    ),
    EnforcedAudienceTestCase(
        name="not_yet_valid_quiet",
        status=LicenseStatus(state=LicenseState.NOT_YET_VALID),
        mode=NoticeMode.QUIET,
        expected=True,
    ),
    EnforcedAudienceTestCase(
        name="expired_quiet",
        status=LicenseStatus(state=LicenseState.EXPIRED),
        mode=NoticeMode.QUIET,
        expected=True,
    ),
    EnforcedAudienceTestCase(
        name="invalid_bad_signature_quiet",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.BAD_SIGNATURE),
        mode=NoticeMode.QUIET,
        expected=True,
    ),
    EnforcedAudienceTestCase(
        name="invalid_internal_error_quiet",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.INTERNAL_ERROR),
        mode=NoticeMode.QUIET,
        expected=False,
    ),
    EnforcedAudienceTestCase(
        name="expiring_quiet",
        status=LicenseStatus(state=LicenseState.EXPIRING),
        mode=NoticeMode.QUIET,
        expected=False,
    ),
    EnforcedAudienceTestCase(
        name="valid_quiet",
        status=LicenseStatus(state=LicenseState.VALID),
        mode=NoticeMode.QUIET,
        expected=False,
    ),
    EnforcedAudienceTestCase(
        name="not_required_quiet",
        status=LicenseStatus(state=LicenseState.NOT_REQUIRED),
        mode=NoticeMode.QUIET,
        expected=False,
    ),
    EnforcedAudienceTestCase(
        name="unlicensed_enforce",
        status=LicenseStatus(state=LicenseState.UNLICENSED),
        mode=NoticeMode.ENFORCE,
        expected=False,
    ),
    EnforcedAudienceTestCase(
        name="invalid_bad_signature_enforce",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.BAD_SIGNATURE),
        mode=NoticeMode.ENFORCE,
        expected=False,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ENFORCED_AUDIENCE_TEST_CASES])
def test_shown_to_all_users_when_enforced(test_case: EnforcedAudienceTestCase) -> None:
    assert shown_to_all_users_when_enforced(status=test_case.status, mode=test_case.mode) is test_case.expected
