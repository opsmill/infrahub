from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.changelog.models import AttributeChangelog
from infrahub.core.constants import DiffAction


@dataclass
class SensitiveAttributeTestCase:
    name: str
    kind: str
    value: Any
    value_previous: Any
    expected_status: DiffAction
    expected_has_updates: bool


SENSITIVE_ATTRIBUTE_TEST_CASES: list[SensitiveAttributeTestCase] = [
    SensitiveAttributeTestCase(
        name="hashed_password_changed",
        kind="HashedPassword",
        value="new_secret",
        value_previous="old_secret",
        expected_status=DiffAction.UPDATED,
        expected_has_updates=True,
    ),
    SensitiveAttributeTestCase(
        name="hashed_password_unchanged",
        kind="HashedPassword",
        value="same_secret",
        value_previous="same_secret",
        expected_status=DiffAction.UNCHANGED,
        expected_has_updates=False,
    ),
    SensitiveAttributeTestCase(
        name="hashed_password_added",
        kind="HashedPassword",
        value="new_secret",
        value_previous=None,
        expected_status=DiffAction.ADDED,
        expected_has_updates=True,
    ),
    SensitiveAttributeTestCase(
        name="hashed_password_removed",
        kind="HashedPassword",
        value=None,
        value_previous="old_secret",
        expected_status=DiffAction.REMOVED,
        expected_has_updates=True,
    ),
    SensitiveAttributeTestCase(
        name="password_changed",
        kind="Password",
        value="new_secret",
        value_previous="old_secret",
        expected_status=DiffAction.UPDATED,
        expected_has_updates=True,
    ),
    SensitiveAttributeTestCase(
        name="password_unchanged",
        kind="Password",
        value="same_secret",
        value_previous="same_secret",
        expected_status=DiffAction.UNCHANGED,
        expected_has_updates=False,
    ),
    SensitiveAttributeTestCase(
        name="password_added",
        kind="Password",
        value="new_secret",
        value_previous=None,
        expected_status=DiffAction.ADDED,
        expected_has_updates=True,
    ),
    SensitiveAttributeTestCase(
        name="password_removed",
        kind="Password",
        value=None,
        value_previous="old_secret",
        expected_status=DiffAction.REMOVED,
        expected_has_updates=True,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in SENSITIVE_ATTRIBUTE_TEST_CASES],
)
def test_sensitive_attribute_update_status(test_case: SensitiveAttributeTestCase) -> None:
    attr = AttributeChangelog(
        name="password",
        value=test_case.value,
        value_previous=test_case.value_previous,
        kind=test_case.kind,
    )

    assert attr.value_update_status == test_case.expected_status
    assert attr.has_updates == test_case.expected_has_updates
