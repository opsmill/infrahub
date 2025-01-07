from datetime import timedelta
from typing import Any
from uuid import UUID

from prefect.events.actions import RunDeployment
from prefect.events.schemas.automations import EventTrigger as PrefectEventTrigger
from prefect.events.schemas.automations import Posture
from pydantic import BaseModel, Field


class EventTrigger(BaseModel):
    events: set = Field(default_factory=set)
    match: dict[str, Any] = Field(default_factory=dict)

    def get_prefect(self) -> PrefectEventTrigger:
        return PrefectEventTrigger(
            posture=Posture.Reactive,
            expect=self.events,
            within=timedelta(0),
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
    previous_names: set = Field(default_factory=set)
    description: str = ""
    trigger: EventTrigger
    actions: list[ExecuteWorkflow]

    def get_deployment_names(self) -> list[str]:
        """Return the name of all deployments used by this trigger"""
        return [action.name for action in self.actions]
