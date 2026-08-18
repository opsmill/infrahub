from dataclasses import dataclass

import pytest
from prefect.events.schemas.events import Event, RelatedResource, Resource
from prefect.settings import PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES, temporary_settings

from infrahub.events.limits import (
    MAX_RUN_CONTEXT_RESOURCES,
    get_prefect_max_related_resources,
    get_related_resource_budget,
)

ENV_VAR = "PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES"


@dataclass
class BudgetCase:
    name: str
    configured_max: str
    expected: int


BUDGET_CASES = [
    BudgetCase(name="one_floored_to_one", configured_max="1", expected=1),  # headroom exceeds the maximum
    BudgetCase(name="twenty_floored_to_one", configured_max="20", expected=1),
    BudgetCase(name="hundred_reserves_the_minimum", configured_max="100", expected=80),  # 100 // 10 < 20
    BudgetCase(name="default_reserves_a_tenth", configured_max="500", expected=450),
    BudgetCase(name="large_reserves_a_tenth", configured_max="5000", expected=4500),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in BUDGET_CASES])
def test_related_resource_budget_reserves_headroom(case: BudgetCase, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR, case.configured_max)
    assert get_related_resource_budget() == case.expected


@dataclass
class SurvivalCase:
    name: str
    configured_max: int


SURVIVAL_CASES = [
    SurvivalCase(name="tenth_reservation", configured_max=500),  # a tenth exceeds the append
    SurvivalCase(name="reservations_meet", configured_max=200),  # a tenth equals the append
    SurvivalCase(name="floor_reservation", configured_max=100),  # the append exceeds a tenth
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SURVIVAL_CASES])
def test_event_on_the_budget_survives_the_prefect_run_context_append(
    case: SurvivalCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An event emitted on the budget must still be accepted once Prefect has enlarged it.

    Prefect's events worker extends the related list in place, which skips the client-side
    validation, so the enlarged event is only ever checked by the Prefect API. Emitting on the
    maximum rather than under it therefore produces an event the API refuses. The cases span both
    sides of the reservation, so the floor is covered as well as the proportional part.
    """
    monkeypatch.setenv(ENV_VAR, str(case.configured_max))
    with temporary_settings({PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES: case.configured_max}):
        event = Event(
            event="infrahub.node.updated",
            resource=Resource({"prefect.resource.id": "infrahub.node.abc"}),
            related=[
                RelatedResource(
                    {"prefect.resource.id": f"infrahub.node.{index}", "prefect.resource.role": "infrahub.related.node"}
                )
                for index in range(get_related_resource_budget())
            ],
        )
        event.related += [
            RelatedResource({"prefect.resource.id": f"prefect.tag.{index}", "prefect.resource.role": "tag"})
            for index in range(MAX_RUN_CONTEXT_RESOURCES)
        ]

        assert len(event.related) <= get_prefect_max_related_resources()
        Event.model_validate(event.model_dump())
