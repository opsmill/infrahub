from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any, TypeVar

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

T = TypeVar("T", bound="TriggerDefinition")


class TriggerComparison(StrEnum):
    MATCH = "match"  # Expected trigger and actual trigger is identical
    REFRESH = "refresh"  # The branch parameters doesn't match, the hash does, refresh in Prefect but don't run triggers
    UPDATE = "update"  # Neither branch or other data points match, update in Prefect and run triggers

    @property
    def update_prefect(self) -> bool:
        return self in {TriggerComparison.REFRESH, TriggerComparison.UPDATE}


class TriggerSetupReport(BaseModel):
    created: list[TriggerDefinition] = Field(default_factory=list)
    refreshed: list[TriggerDefinition] = Field(default_factory=list)
    updated: list[TriggerDefinition] = Field(default_factory=list)
    deleted: list[Automation] = Field(default_factory=list)
    unchanged: list[TriggerDefinition] = Field(default_factory=list)

    @property
    def in_use_count(self) -> int:
        return len(self.created + self.updated + self.unchanged + self.refreshed)

    def add_with_comparison(self, trigger: TriggerDefinition, comparison: TriggerComparison) -> None:
        match comparison:
            case TriggerComparison.UPDATE:
                self.updated.append(trigger)
            case TriggerComparison.REFRESH:
                self.refreshed.append(trigger)
            case TriggerComparison.MATCH:
                self.unchanged.append(trigger)

    def _created_triggers_with_type(self, trigger_type: type[T]) -> list[T]:
        return [trigger for trigger in self.created if isinstance(trigger, trigger_type)]

    def _refreshed_triggers_with_type(self, trigger_type: type[T]) -> list[T]:
        return [trigger for trigger in self.refreshed if isinstance(trigger, trigger_type)]

    def _unchanged_triggers_with_type(self, trigger_type: type[T]) -> list[T]:
        return [trigger for trigger in self.unchanged if isinstance(trigger, trigger_type)]

    def _updated_triggers_with_type(self, trigger_type: type[T]) -> list[T]:
        return [trigger for trigger in self.updated if isinstance(trigger, trigger_type)]

    def triggers_with_type(self, trigger_type: type[T]) -> list[T]:
        """Return all triggers that match the specified type.

        Args:
            trigger_type: A TriggerDefinition class or subclass to filter by

        Returns:
            List of triggers of the specified type from all categories
        """
        created = self._created_triggers_with_type(trigger_type=trigger_type)
        updated = self._updated_triggers_with_type(trigger_type=trigger_type)
        refreshed = self._refreshed_triggers_with_type(trigger_type=trigger_type)
        unchanged = self._unchanged_triggers_with_type(trigger_type=trigger_type)
        return created + updated + refreshed + unchanged

    def modified_triggers_with_type(self, trigger_type: type[T]) -> list[T]:
        """Return all created and updated triggers that match the specified type.

        Args:
            trigger_type: A TriggerDefinition class or subclass to filter by

        Returns:
            List of triggers of the specified type from both created and updated lists
        """
        created = self._created_triggers_with_type(trigger_type=trigger_type)
        updated = self._updated_triggers_with_type(trigger_type=trigger_type)
        return created + updated


class TriggerType(StrEnum):
    ACTION_TRIGGER_RULE = "action_trigger_rule"
    BUILTIN = "builtin"
    WEBHOOK = "webhook"
    COMPUTED_ATTR_JINJA2 = "computed_attr_jinja2"
    COMPUTED_ATTR_PYTHON = "computed_attr_python"
    COMPUTED_ATTR_PYTHON_QUERY = "computed_attr_python_query"
    DISPLAY_LABEL_JINJA2 = "display_label_jinja2"
    HUMAN_FRIENDLY_ID = "human_friendly_id"
    # OBJECT = "object"

    @property
    def is_branch_specific(self) -> bool:
        return self in {
            TriggerType.COMPUTED_ATTR_JINJA2,
            TriggerType.COMPUTED_ATTR_PYTHON,
            TriggerType.COMPUTED_ATTR_PYTHON_QUERY,
            TriggerType.DISPLAY_LABEL_JINJA2,
            TriggerType.HUMAN_FRIENDLY_ID,
        }


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
