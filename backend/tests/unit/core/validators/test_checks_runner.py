"""Unit tests for the validator checks-runner's event emission.

These pin down which validator lifecycle events the checks-runner emits, and — importantly —
which it does not. See the test docstring for why the ``started``/terminal split matters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.core.validators.checks_runner import run_checks_and_update_validator
from infrahub.events.validator_action import ValidatorFailedEvent, ValidatorPassedEvent, ValidatorStartedEvent
from tests.adapters.event import MemoryInfrahubEvent

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from infrahub_sdk.protocols import CoreValidator


@dataclass
class _Attr:
    """Mutable stand-in for an SDK node attribute, exposing a single ``value``."""

    value: object | None = None


class FakeValidator:
    """Minimal stand-in for an SDK ``CoreValidator``.

    Which events fire depends only on the check results, not on persistence, so a fake with a
    no-op ``save`` is enough — no real node or live API needed.
    """

    def __init__(self, *, validator_id: str, kind: str) -> None:
        self.id = validator_id
        self._kind = kind
        self.state = _Attr()
        self.conclusion = _Attr(ValidatorConclusion.UNKNOWN.value)
        self.started_at = _Attr()
        self.completed_at = _Attr()
        self.save_count = 0

    def get_kind(self) -> str:
        return self._kind

    async def save(self) -> None:
        self.save_count += 1


async def _check(conclusion: ValidatorConclusion) -> ValidatorConclusion:
    return conclusion


@dataclass
class CheckRunnerCase:
    name: str
    check_results: list[ValidatorConclusion]
    expected_events: list[type]
    expected_conclusion: str


CASES = [
    CheckRunnerCase(
        name="no_checks_concludes_success",
        check_results=[],
        expected_events=[ValidatorPassedEvent],
        expected_conclusion=ValidatorConclusion.SUCCESS.value,
    ),
    CheckRunnerCase(
        name="all_checks_pass",
        check_results=[ValidatorConclusion.SUCCESS, ValidatorConclusion.SUCCESS],
        expected_events=[ValidatorPassedEvent],
        expected_conclusion=ValidatorConclusion.SUCCESS.value,
    ),
    CheckRunnerCase(
        name="a_failing_check_fails_the_validator",
        check_results=[ValidatorConclusion.SUCCESS, ValidatorConclusion.FAILURE],
        expected_events=[ValidatorFailedEvent],
        expected_conclusion=ValidatorConclusion.FAILURE.value,
    ),
]


def _make_context() -> InfrahubContext:
    return InfrahubContext(
        branch=BranchContext(name="main", id="00000000-0000-0000-0000-000000000000"),
        account=AccountSession(account_id="00000000-0000-0000-0000-000000000001", auth_type=AuthType.API),
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
async def test_run_checks_and_update_validator_emits_terminal_event_but_never_started(
    case: CheckRunnerCase,
) -> None:
    """The checks-runner emits a terminal (passed/failed) event but never a ``started`` event.

    ``started`` comes from a separate step, so a validator that concludes without going through
    this function emits ``started`` but no terminal event — which is why a successful validator
    can be counted in ``checks_started`` yet not ``checks_passed``.
    """
    event_service = MemoryInfrahubEvent()
    validator = FakeValidator(validator_id="18b00000-0000-0000-0000-0000000000aa", kind="CoreDataValidator")
    checks = cast(
        "list[Coroutine[Any, None, ValidatorConclusion]]",
        [_check(result) for result in case.check_results],
    )

    await run_checks_and_update_validator(
        checks=checks,
        validator=cast("CoreValidator", validator),
        context=_make_context(),
        event_service=event_service,
        proposed_change_id="18b00000-0000-0000-0000-0000000000bb",
    )

    emitted = [type(event) for event in event_service.events]
    assert emitted == case.expected_events
    # The crux: the checks-runner is the sole emitter of terminal events and never emits started.
    assert ValidatorStartedEvent not in emitted
    # The validator did complete — so a completed-successfully validator still emits no started.
    assert validator.state.value == ValidatorState.COMPLETED.value
    assert validator.conclusion.value == case.expected_conclusion
