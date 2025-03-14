from infrahub.events.branch_action import BranchDeletedEvent
from infrahub.events.repository_action import CommitUpdatedEvent
from infrahub.events.schema_action import SchemaUpdatedEvent
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_SETUP_JINJA2,
    COMPUTED_ATTRIBUTE_SETUP_PYTHON,
)

TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT = BuiltinTriggerDefinition(
    name="computed-attribute-python-setup-on-commit",
    trigger=EventTrigger(events={CommitUpdatedEvent.event_name}),
    actions=[
        ExecuteWorkflow(
            workflow=COMPUTED_ATTRIBUTE_SETUP_PYTHON,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                "commit": "{{ event.payload['commit'] }}",
                "event_name": "{{ event.event }}",
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
            },
        )
    ],
)

TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA = BuiltinTriggerDefinition(
    name="computed-attribute-setup-all",
    trigger=EventTrigger(events={SchemaUpdatedEvent.event_name, BranchDeletedEvent.event_name}),
    actions=[
        ExecuteWorkflow(
            workflow=COMPUTED_ATTRIBUTE_SETUP_JINJA2,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                "event_name": "{{ event.event }}",
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
            },
        ),
        ExecuteWorkflow(
            workflow=COMPUTED_ATTRIBUTE_SETUP_PYTHON,
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
