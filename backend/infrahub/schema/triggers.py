from infrahub.events.schema_action import SchemaUpdatedEvent
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow, jinja_parameter
from infrahub.workflows.catalogue import SCHEMA_UPDATED

TRIGGER_SCHEMA_UPDATED = BuiltinTriggerDefinition(
    name="schema-updated-trigger",
    trigger=EventTrigger(
        events={SchemaUpdatedEvent.event_name},
    ),
    actions=[
        ExecuteWorkflow(
            workflow=SCHEMA_UPDATED,
            parameters={
                "branch_name": jinja_parameter("{{ event.payload['data']['branch_name'] }}"),
                "schema_hash": jinja_parameter("{{ event.payload['data']['schema_hash'] }}"),
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
            },
        ),
    ],
)
