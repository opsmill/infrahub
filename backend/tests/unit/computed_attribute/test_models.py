import uuid
from datetime import timedelta

from prefect.events.schemas.automations import Automation, EventTrigger, Posture

from infrahub.computed_attribute.constants import AUTOMATION_NAME
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
        generate_automation(name=AUTOMATION_NAME.format(identifier="AAAAA", scope="default")),
        generate_automation(name=AUTOMATION_NAME.format(identifier="AAAAA", scope="yyyy")),
        generate_automation(name=AUTOMATION_NAME.format(identifier="BBBBB", scope="default")),
        generate_automation(name="anothername"),
    ]

    obj = ComputedAttributeAutomations.from_prefect(automations=automations)

    assert obj.has(identifier="AAAAA", scope="default")
    assert obj.has(identifier="AAAAA", scope="yyyy")
    assert obj.has(identifier="BBBBB", scope="default")
