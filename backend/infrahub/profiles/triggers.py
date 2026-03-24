from infrahub.events.branch_action import BranchDeletedEvent
from infrahub.events.schema_action import SchemaUpdatedEvent
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import PROFILE_REFRESH_SETUP

TRIGGER_PROFILE_REFRESH_SETUP = BuiltinTriggerDefinition(
    name="profile-refresh-setup-all",
    trigger=EventTrigger(events={SchemaUpdatedEvent.event_name, BranchDeletedEvent.event_name}),
    actions=[
        ExecuteWorkflow(
            workflow=PROFILE_REFRESH_SETUP,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                "event_name": "{{ event.event }}",
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
            },
        ),
    ],
)
