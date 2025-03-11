from infrahub.events.branch_action import BranchCreatedEvent, BranchDeletedEvent
from infrahub.events.repository_action import CommitUpdatedEvent
from infrahub.events.schema_action import SchemaUpdatedEvent
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_REMOVE_PYTHON,
    COMPUTED_ATTRIBUTE_SETUP,
    COMPUTED_ATTRIBUTE_SETUP_PYTHON,
)

TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_BRANCH = BuiltinTriggerDefinition(
    name="computed-attribute-python-setup-on-branch-creation",
    previous_names={"Trigger-schema-update-event"},
    description="Trigger actions on branch create event",
    trigger=EventTrigger(events={BranchCreatedEvent.event_name}),
    actions=[
        ExecuteWorkflow(
            workflow=COMPUTED_ATTRIBUTE_SETUP_PYTHON,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                "trigger_updates": False,
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
            },
        )
    ],
)

TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT = BuiltinTriggerDefinition(
    name="computed-attribute-python-setup-on-commit",
    description="Trigger actions on branch create event",
    trigger=EventTrigger(events={CommitUpdatedEvent.event_name}),
    actions=[
        ExecuteWorkflow(
            workflow=COMPUTED_ATTRIBUTE_SETUP_PYTHON,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                "commit": "{{ event.payload['commit'] }}",
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
            },
        )
    ],
)

TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_CLEAN_BRANCH = BuiltinTriggerDefinition(
    name="computed-attribute-python-cleanup-on-branch-deletion",
    description="Trigger actions on branch delete event",
    trigger=EventTrigger(events={BranchDeletedEvent.event_name}),
    actions=[
        ExecuteWorkflow(
            workflow=COMPUTED_ATTRIBUTE_REMOVE_PYTHON,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
            },
        )
    ],
)

TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA = BuiltinTriggerDefinition(
    name="computed-attribute-all-setup-on-schema-update",
    trigger=EventTrigger(events={SchemaUpdatedEvent.event_name}),
    actions=[
        ExecuteWorkflow(
            workflow=COMPUTED_ATTRIBUTE_SETUP,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
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
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
            },
        ),
    ],
)
