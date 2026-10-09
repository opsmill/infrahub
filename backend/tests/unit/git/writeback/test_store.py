from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.constants import RepositoryDeliveryFailureCause, RepositoryDeliveryStatus
from infrahub.exceptions import DeliveryStateUnreadableError
from infrahub.git.writeback.models import DeliveryQueue, HeldRegeneration
from infrahub.git.writeback.store import _stored, _stored_member


@dataclass
class UnreadableJsonTestCase:
    name: str
    attribute: str
    model: type[DeliveryQueue | HeldRegeneration]
    value: dict[str, Any]


UNREADABLE_JSON_TEST_CASES: list[UnreadableJsonTestCase] = [
    UnreadableJsonTestCase(
        name="field_of_the_wrong_type",
        attribute="delivery_queue",
        model=DeliveryQueue,
        value={"format": 1, "version": "not a number"},
    ),
    UnreadableJsonTestCase(
        name="format_of_a_later_release",
        attribute="delivery_held_regeneration",
        model=HeldRegeneration,
        value={"format": 2},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in UNREADABLE_JSON_TEST_CASES])
def test_stored_json_that_does_not_match_its_model_names_the_repository_and_the_attribute(
    test_case: UnreadableJsonTestCase,
) -> None:
    with pytest.raises(
        DeliveryStateUnreadableError,
        match=(
            rf"^The stored value of {test_case.attribute} on repository net-repo does not match its expected shape\.$"
        ),
    ):
        _stored(
            stored={test_case.attribute: test_case.value},
            attribute=test_case.attribute,
            model=test_case.model,
            repository_name="net-repo",
        )


@dataclass
class UnknownMemberTestCase:
    name: str
    attribute: str
    enum: type[RepositoryDeliveryStatus | RepositoryDeliveryFailureCause]
    value: str


UNKNOWN_MEMBER_TEST_CASES: list[UnknownMemberTestCase] = [
    UnknownMemberTestCase(name="status", attribute="delivery_status", enum=RepositoryDeliveryStatus, value="paused"),
    UnknownMemberTestCase(
        name="failure_cause",
        attribute="delivery_failure_cause",
        enum=RepositoryDeliveryFailureCause,
        value="mirror-lagging",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in UNKNOWN_MEMBER_TEST_CASES])
def test_stored_choice_that_is_not_a_member_names_the_repository_and_the_attribute(
    test_case: UnknownMemberTestCase,
) -> None:
    with pytest.raises(
        DeliveryStateUnreadableError,
        match=(
            rf"^The stored value of {test_case.attribute} on repository net-repo does not match its expected shape\.$"
        ),
    ):
        _stored_member(
            stored={test_case.attribute: test_case.value},
            attribute=test_case.attribute,
            enum=test_case.enum,
            repository_name="net-repo",
        )
