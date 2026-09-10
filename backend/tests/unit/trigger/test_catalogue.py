from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.trigger import catalogue
from infrahub.trigger.catalogue import builtin_triggers
from infrahub.trigger.models import ProactiveEventTrigger
from infrahub.trigger.system import (
    TRIGGER_CRASH_ZOMBIE_FLOWS,
    ZOMBIE_HEARTBEAT_WINDOW,
    ZOMBIE_WATCH_ENDING_EVENTS,
    ZOMBIE_WATCH_RENEWING_EVENTS,
)
from infrahub.webhook.constants import WEBHOOK_SEND_RETRY_DELAY_SECONDS

if TYPE_CHECKING:
    from infrahub.trigger.models import TriggerDefinition


@pytest.mark.parametrize("trigger", [pytest.param(trigger, id=trigger.name) for trigger in builtin_triggers])
def test_builtin_trigger_definition(trigger: TriggerDefinition) -> None:
    """Validate that the actions associated with the trigger matches the definition of the workflow."""
    trigger.validate_actions()


def test_builtin_triggers_sorted() -> None:
    names = sorted(name for name in dir(catalogue) if name.isupper())
    ordered_triggers = [getattr(catalogue, name) for name in names]
    assert ordered_triggers == builtin_triggers, "The list of triggers isn't sorted alphabetically"


def test_zombie_watch_only_ends_on_a_terminal_state() -> None:
    """Every event that does not end the zombie watch must renew the countdown.

    A proactive trigger only restarts its countdown for an event listed in `after`. An event that
    is merely expected satisfies the window instead, so it expires without firing and the run is
    left unwatched. That is the right outcome for a run that has finished and wrong for any event
    that means the run is still alive, so the expected set may only ever add terminal states on
    top of the renewing ones.
    """
    trigger = TRIGGER_CRASH_ZOMBIE_FLOWS.trigger
    assert isinstance(trigger, ProactiveEventTrigger)

    assert trigger.after == ZOMBIE_WATCH_RENEWING_EVENTS
    assert trigger.events - ZOMBIE_WATCH_ENDING_EVENTS == trigger.after, (
        "an expected event that is not terminal must also be in `after`, or it permanently "
        "disarms zombie detection for that run"
    )


def test_zombie_watch_window_outlasts_the_longest_retry_backoff() -> None:
    """The countdown must not lapse while a run legitimately waits out its retry backoff."""
    assert ZOMBIE_HEARTBEAT_WINDOW.total_seconds() > WEBHOOK_SEND_RETRY_DELAY_SECONDS
