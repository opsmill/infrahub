from datetime import timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from prefect.events.actions import RunDeployment
from prefect.events.schemas.automations import EventTrigger as PrefectEventTrigger
from prefect.events.schemas.automations import Posture
from prefect.events.schemas.events import ResourceSpecification
from pydantic import BaseModel, Field

from .constants import NAME_SEPARATOR


class TriggerType(str, Enum):
    BUILTIN = "builtin"
    # OBJECT = "object"
    # COMPUTED_ATTR = "computed_attr"


class EventTrigger(BaseModel):
    events: set = Field(default_factory=set)
    match: dict[str, Any] = Field(default_factory=dict)
    match_related: dict[str, Any] = Field(default_factory=dict)

    def get_prefect(self) -> PrefectEventTrigger:
        return PrefectEventTrigger(
            posture=Posture.Reactive,
            expect=self.events,
            within=timedelta(0),
            match=ResourceSpecification(self.match),
            match_related=ResourceSpecification(self.match_related),
            threshold=1,
        )


class ExecuteWorkflow(BaseModel):
    name: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    def get_prefect(self, mapping: dict[str, UUID]) -> RunDeployment:
        deployment_id = mapping[self.name]

        return RunDeployment(
            source="selected",
            deployment_id=deployment_id,
            parameters=self.parameters,
            job_variables={},
        )


class TriggerDefinition(BaseModel):
    name: str
    type: TriggerType
    previous_names: set = Field(default_factory=set)
    description: str = ""
    trigger: EventTrigger
    actions: list[ExecuteWorkflow]

    def get_deployment_names(self) -> list[str]:
        """Return the name of all deployments used by this trigger"""
        return [action.name for action in self.actions]

    def generate_name(self) -> str:
        return f"{self.type.value}{NAME_SEPARATOR}{self.name}"


class BuiltinTriggerDefinition(TriggerDefinition):
    type: TriggerType = TriggerType.BUILTIN
