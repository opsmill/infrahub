from __future__ import annotations

from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

from prefect.events.actions import RunDeployment
from prefect.events.schemas.automations import Automation, Posture
from prefect.events.schemas.automations import EventTrigger as PrefectEventTrigger
from prefect.events.schemas.events import ResourceSpecification
from pydantic import BaseModel, Field

from infrahub import __version__
from infrahub.workflows.models import WorkflowDefinition  # noqa: TC001

from .constants import NAME_SEPARATOR

if TYPE_CHECKING:
    from uuid import UUID


class TriggerSetupReport(BaseModel):
    created: list[TriggerDefinition] = Field(default_factory=list)
    updated: list[TriggerDefinition] = Field(default_factory=list)
    deleted: list[Automation] = Field(default_factory=list)
    unchanged: list[TriggerDefinition] = Field(default_factory=list)

    @property
    def in_use_count(self) -> int:
        return len(self.created + self.updated + self.unchanged)


class TriggerType(str, Enum):
    ACTION_TRIGGER_RULE = "action_trigger_rule"
    BUILTIN = "builtin"
    WEBHOOK = "webhook"
    COMPUTED_ATTR_JINJA2 = "computed_attr_jinja2"
    COMPUTED_ATTR_PYTHON = "computed_attr_python"
    COMPUTED_ATTR_PYTHON_QUERY = "computed_attr_python_query"
    # OBJECT = "object"


def _match_related_dict() -> dict:
    # Make Mypy happy as match related is a dict[str, Any] | list[dict[str, Any]]
    return {}


class EventTrigger(BaseModel):
    events: set = Field(default_factory=set)
    match: dict[str, Any] = Field(default_factory=dict)
    match_related: dict[str, Any] | list[dict[str, Any]] = Field(default_factory=_match_related_dict)

    def get_prefect(self) -> PrefectEventTrigger:
        return PrefectEventTrigger(
            posture=Posture.Reactive,
            expect=self.events,
            within=timedelta(0),
            match=ResourceSpecification(self.match),
            match_related=self.related_resource_specification,
            threshold=1,
        )

    @property
    def related_resource_specification(self) -> ResourceSpecification | list[ResourceSpecification]:
        if isinstance(self.match_related, dict):
            return ResourceSpecification(self.match_related)

        if len(self.match_related) == 1:
            return ResourceSpecification(self.match_related[0])

        return [ResourceSpecification(related_match) for related_match in self.match_related]


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

    def get_description(self) -> str:
        return f"Automation for Trigger {self.name} of type {self.type.value} (v{__version__})"

    def generate_name(self) -> str:
        return f"{self.type.value}{NAME_SEPARATOR}{self.name}"

    def validate_actions(self) -> None:
        for action in self.actions:
            action.validate_parameters()


class TriggerBranchDefinition(TriggerDefinition):
    branch: str

    def generate_name(self) -> str:
        return f"{self.type.value}{NAME_SEPARATOR}{self.branch}{NAME_SEPARATOR}{self.name}"


class BuiltinTriggerDefinition(TriggerDefinition):
    type: TriggerType = TriggerType.BUILTIN
