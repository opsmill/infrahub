from __future__ import annotations

from typing import TYPE_CHECKING, Self

from infrahub.core.registry import registry
from infrahub.events import NodeUpdatedEvent
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import EventTrigger, ExecuteWorkflow, TriggerBranchDefinition, TriggerType

if TYPE_CHECKING:
    from infrahub.workflows.models import WorkflowDefinition


class ProfileRefreshTriggerDefinition(TriggerBranchDefinition):
    """Trigger definition for profile refresh when profile attributes/relationships change."""

    type: TriggerType = TriggerType.PROFILE
    profile_kind: str

    @classmethod
    def from_profile_schema(
        cls,
        branch: str,
        profile_kind: str,
        trigger_fields: list[str],
        workflow: WorkflowDefinition,
        branches_out_of_scope: list[str] | None = None,
    ) -> Self:
        """Create a trigger definition for profile refresh when profile attributes/relationships change."""
        event_trigger = EventTrigger()
        event_trigger.events.add(NodeUpdatedEvent.event_name)
        event_trigger.match = {"infrahub.node.kind": profile_kind}

        if branches_out_of_scope:
            event_trigger.match["infrahub.branch.name"] = [f"!{b}" for b in branches_out_of_scope]
        elif branch != registry.default_branch:
            event_trigger.match["infrahub.branch.name"] = branch

        event_trigger.match_related = {
            "prefect.resource.role": ["infrahub.node.attribute_update", "infrahub.node.relationship_update"],
            "infrahub.field.name": trigger_fields,
        }

        workflow_action = ExecuteWorkflow(
            workflow=workflow,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                "profile_kind": profile_kind,
                "profile_id": "{{ event.resource['infrahub.node.id'] }}",
                "context": {
                    "__prefect_kind": "json",
                    "value": {
                        "__prefect_kind": "jinja",
                        "template": "{{ event.payload['context'] | tojson }}",
                    },
                },
            },
        )

        return cls(
            name=f"{profile_kind}{NAME_SEPARATOR}refresh",
            branch=branch,
            profile_kind=profile_kind,
            trigger=event_trigger,
            actions=[workflow_action],
        )
