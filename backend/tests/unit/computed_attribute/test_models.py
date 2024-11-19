import uuid
from datetime import timedelta

from prefect.events.schemas.automations import Automation, EventTrigger, Posture

from infrahub.computed_attribute.constants import (
    PROCESS_AUTOMATION_NAME,
    PROCESS_AUTOMATION_NAME_PREFIX,
    QUERY_AUTOMATION_NAME,
    QUERY_AUTOMATION_NAME_PREFIX,
)
from infrahub.computed_attribute.models import ComputedAttributeAutomations


def generate_automation(
    name: str, description: str = "", trigger: EventTrigger | None = None, actions: list | None = None
) -> Automation:
    default_trigger = EventTrigger(
        posture=Posture.Reactive,
        expect={"infrahub.node.*"},
        within=timedelta(0),
        threshold=1,
    )

    return Automation(
        id=uuid.uuid4(),
        name=name,
        description=description,
        enabled=True,
        trigger=trigger or default_trigger,
        actions=actions or [],
    )


async def test_load_from_prefect():
    automations: list[Automation] = [
        generate_automation(name=PROCESS_AUTOMATION_NAME.format(identifier="AAAAA", scope="default")),
        generate_automation(name=PROCESS_AUTOMATION_NAME.format(identifier="AAAAA", scope="yyyy")),
        generate_automation(name=PROCESS_AUTOMATION_NAME.format(identifier="BBBBB", scope="default")),
        generate_automation(name=QUERY_AUTOMATION_NAME.format(identifier="CCCCC", scope="default")),
        generate_automation(name="anothername"),
    ]

    obj = ComputedAttributeAutomations.from_prefect(automations=automations, prefix=PROCESS_AUTOMATION_NAME_PREFIX)
    query_obj = ComputedAttributeAutomations.from_prefect(automations=automations, prefix=QUERY_AUTOMATION_NAME_PREFIX)

    assert obj.has(identifier="AAAAA", scope="default")
    assert obj.has(identifier="AAAAA", scope="yyyy")
    assert obj.has(identifier="BBBBB", scope="default")
    assert not obj.has(identifier="CCCCC", scope="default")

    query_obj = ComputedAttributeAutomations.from_prefect(automations=automations, prefix=QUERY_AUTOMATION_NAME_PREFIX)
    assert not query_obj.has(identifier="AAAAA", scope="default")
    assert query_obj.has(identifier="CCCCC", scope="default")
