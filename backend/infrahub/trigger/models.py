from __future__ import annotations

from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

from prefect.events.actions import RunDeployment
from prefect.events.schemas.automations import EventTrigger as PrefectEventTrigger
from prefect.events.schemas.automations import Posture
from prefect.events.schemas.events import ResourceSpecification
from pydantic import BaseModel, Field

from infrahub.workflows.models import WorkflowDefinition  # noqa: TC001

from .constants import NAME_SEPARATOR

if TYPE_CHECKING:
    from uuid import UUID


class TriggerType(str, Enum):
    BUILTIN = "builtin"
    WEBHOOK = "webhook"
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
    workflow: WorkflowDefinition
    parameters: dict[str, Any] = Field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.workflow.name

    def get_prefect(self, mapping: dict[str, UUID]) -> RunDeployment:
        deployment_id = mapping[self.name]
        return self.get(deployment_id)

    def get(self, id: UUID) -> RunDeployment:
        return RunDeployment(
            source="selected",
            deployment_id=id,
            parameters=self.parameters,
            job_variables={},
        )

    def validate_parameters(self) -> None:
        if not self.parameters:
            return

        workflow_params = self.workflow.get_parameters()
        workflow_required_params = [p.name for p in workflow_params.values() if p.required]
        trigger_params = list(self.parameters.keys())

        missing_required_params = set(workflow_required_params) - set(trigger_params)
        wrong_params = set(trigger_params) - set(workflow_params)

        if missing_required_params:
            raise ValueError(
                f"Missing required parameters: {missing_required_params} for workflow {self.workflow.name}"
            )

        if wrong_params:
            raise ValueError(f"Workflow {self.workflow.name} doesn't support parameters: {wrong_params}")


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

    def validate_actions(self) -> None:
        for action in self.actions:
            action.validate_parameters()


class BuiltinTriggerDefinition(TriggerDefinition):
    type: TriggerType = TriggerType.BUILTIN
