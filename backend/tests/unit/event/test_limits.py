from dataclasses import dataclass

import pytest
from prefect.events.schemas.events import Event, RelatedResource, Resource
from prefect.settings import (
    PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES,
    PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES,
    temporary_settings,
)
from prefect.settings.legacy import Setting  # the type of the module-level PREFECT_* accessors
from prefect.settings.models.server.events import ServerEventsSettings

from infrahub.events.limits import (
    MAX_RUN_CONTEXT_RESOURCES,
    PREFECT_DEFAULT_MAX_RELATED_RESOURCES,
    get_prefect_max_related_resources,
    get_related_resource_budget,
    get_submission_chunk_size,
)

# Prefect resolves its settings once at import, so these cases drive the maximum through
# temporary_settings - the same path an operator's profile or configuration file takes.
# PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES is the name the Infrahub image sets and
# PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES is the alias; they are two names for one setting.


@dataclass
class ChunkSizeCase:
    name: str
    configured_max: int
    expected: int


CHUNK_SIZE_CASES = [
    ChunkSizeCase(name="one_floored_to_one", configured_max=1, expected=1),  # 1 // 2 == 0 without the floor
    ChunkSizeCase(name="two_floored_to_one", configured_max=2, expected=1),
    ChunkSizeCase(name="ten_halved", configured_max=10, expected=5),
    ChunkSizeCase(name="image_maximum_halved", configured_max=500, expected=250),
]


@pytest.mark.parametrize("case", CHUNK_SIZE_CASES, ids=lambda case: case.name)
def test_submission_chunk_size_is_floored_at_one(case: ChunkSizeCase) -> None:
    with temporary_settings({PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES: case.configured_max}):
        assert get_submission_chunk_size() == case.expected


@dataclass
class BudgetCase:
    name: str
    configured_max: int
    expected: int


BUDGET_CASES = [
    BudgetCase(name="one_floored_to_one", configured_max=1, expected=1),  # headroom exceeds the maximum
    BudgetCase(name="twenty_floored_to_one", configured_max=20, expected=1),
    # 100 is Prefect's own default, so this case also pins the budget an unconfigured deployment gets.
    BudgetCase(name="hundred_reserves_the_minimum", configured_max=100, expected=80),  # 100 // 10 < 20
    BudgetCase(name="image_maximum_reserves_a_tenth", configured_max=500, expected=450),
    BudgetCase(name="large_reserves_a_tenth", configured_max=5000, expected=4500),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in BUDGET_CASES])
def test_related_resource_budget_reserves_headroom(case: BudgetCase) -> None:
    with temporary_settings({PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES: case.configured_max}):
        assert get_related_resource_budget() == case.expected


def test_fallback_is_pinned_to_the_prefect_default() -> None:
    """The fallback tracks Prefect's own default rather than a value copied from the image.

    A fallback above what Prefect enforces makes Infrahub truncate to a budget Prefect refuses,
    and the event is then dropped without an error. Reading the default off the Prefect settings
    model rather than restating the number here means a change to it fails this test instead of
    silently reopening that gap.
    """
    prefect_default = ServerEventsSettings.model_fields["maximum_related_resources"].default

    assert prefect_default == PREFECT_DEFAULT_MAX_RELATED_RESOURCES

    with temporary_settings({PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES: prefect_default}):
        assert get_prefect_max_related_resources() == PREFECT_DEFAULT_MAX_RELATED_RESOURCES


@dataclass
class AliasCase:
    name: str
    setting: Setting
    configured_max: int


ALIAS_CASES = [
    AliasCase(name="server_prefixed_name", setting=PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES, configured_max=500),
    AliasCase(name="unprefixed_name", setting=PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES, configured_max=250),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in ALIAS_CASES])
def test_maximum_follows_either_setting_alias(case: AliasCase) -> None:
    """Both names Prefect accepts for the limit must reach Infrahub.

    An operator who sets either name, or configures Prefect through a profile, moves the cap
    Prefect enforces; Infrahub has to move with it or it truncates against a stale ceiling.
    """
    with temporary_settings({case.setting: case.configured_max}):
        assert get_prefect_max_related_resources() == case.configured_max


@pytest.mark.parametrize("configured_max", [0, -1, -500], ids=["zero", "negative_one", "negative"])
def test_non_positive_maximum_falls_back_to_the_default(configured_max: int) -> None:
    """A maximum Prefect could not meaningfully enforce must not produce a nonsensical budget.

    This does not rescue delivery - with a maximum of zero Prefect rejects every event carrying a
    related resource regardless of what Infrahub sends. It keeps the budget and chunk size derived
    from a sensible ceiling rather than from zero or a negative number.
    """
    with temporary_settings({PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES: configured_max}):
        assert get_prefect_max_related_resources() == PREFECT_DEFAULT_MAX_RELATED_RESOURCES
        assert get_related_resource_budget() >= 1
        assert get_submission_chunk_size() >= 1


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
def test_event_on_the_budget_survives_the_prefect_run_context_append(case: SurvivalCase) -> None:
    """An event emitted on the budget must still be accepted once Prefect has enlarged it.

    Prefect's events worker extends the related list in place, which skips the client-side
    validation, so the enlarged event is only ever checked by the Prefect API. Emitting on the
    maximum rather than under it therefore produces an event the API refuses. The cases span both
    sides of the reservation, so the floor is covered as well as the proportional part.
    """
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
