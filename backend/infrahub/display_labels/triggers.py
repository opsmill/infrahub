from infrahub.events.branch_action import BranchDeletedEvent
from infrahub.events.schema_action import SchemaUpdatedEvent
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import DISPLAY_LABELS_SETUP_JINJA2

TRIGGER_DISPLAY_LABELS_ALL_SCHEMA = BuiltinTriggerDefinition(
    name="display-labels-setup-all",
    trigger=EventTrigger(events={SchemaUpdatedEvent.event_name, BranchDeletedEvent.event_name}),
    actions=[
        ExecuteWorkflow(
            workflow=DISPLAY_LABELS_SETUP_JINJA2,
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
