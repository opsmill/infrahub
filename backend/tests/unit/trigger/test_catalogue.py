from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.trigger import catalogue
from infrahub.trigger.catalogue import builtin_triggers

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
