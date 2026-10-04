from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.license.models import LicenseState, LicenseStatus, Notice, NoticeAudience, NoticeMode
from infrahub.license.status import notice_for

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
    assert notice_for(status=LicenseStatus(state=test_case.state), mode=test_case.mode) == test_case.expected


def test_every_state_and_mode_is_covered() -> None:
    """Adding a state or a mode must come with its expected notice."""
    covered = {(test_case.state, test_case.mode) for test_case in NOTICE_TEST_CASES}

    assert covered == {(state, mode) for state in LicenseState for mode in NoticeMode}
