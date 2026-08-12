from infrahub.core.constants import InfrahubKind
from infrahub.events.branch_action import BranchDeletedEvent
from infrahub.events.constants import NODE_ORIGIN_LABEL, NodeMutationOrigin
from infrahub.events.node_action import NodeCreatedEvent, NodeDeletedEvent, NodeUpdatedEvent
from infrahub.events.schema_action import SchemaUpdatedEvent
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow, jinja_parameter
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM_LIFECYCLE,
    COMPUTED_ATTRIBUTE_SETUP_JINJA2,
    COMPUTED_ATTRIBUTE_SETUP_PYTHON,
)


def _lifecycle_action() -> ExecuteWorkflow:
    return ExecuteWorkflow(
        workflow=COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM_LIFECYCLE,
        parameters={
            "branch_name": jinja_parameter("{{ event.resource['infrahub.branch.name'] }}"),
            "transform_id": jinja_parameter("{{ event.resource['infrahub.node.id'] }}"),
            "action": jinja_parameter("{{ event.resource['infrahub.node.action'] }}"),
            "event_name": jinja_parameter("{{ event.event }}"),
            "context": {
                "__prefect_kind": "json",
                "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
            },
        },
    )


# origin=LIVE keeps merge/rebase replays out; the kind scope keeps the recompute write (which
# targets the attribute's own node kind, not the transform) from re-firing these triggers.
_LIFECYCLE_MATCH = {
    "infrahub.node.kind": InfrahubKind.TRANSFORMPYTHON,
    NODE_ORIGIN_LABEL: NodeMutationOrigin.LIVE.value,
}

TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_CREATED = BuiltinTriggerDefinition(
    name="computed-attribute-python-transform-created",
    trigger=EventTrigger(
        events={NodeCreatedEvent.event_name},
        match=dict(_LIFECYCLE_MATCH),
    ),
    actions=[_lifecycle_action()],
)

TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_UPDATED = BuiltinTriggerDefinition(
    name="computed-attribute-python-transform-updated",
    trigger=EventTrigger(
        events={NodeUpdatedEvent.event_name},
        match=dict(_LIFECYCLE_MATCH),
        match_related={
            "prefect.resource.role": ["infrahub.node.attribute_update"],
            "infrahub.field.name": ["fingerprint"],
        },
    ),
    actions=[_lifecycle_action()],
)

TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_DELETED = BuiltinTriggerDefinition(
    name="computed-attribute-python-transform-deleted",
    trigger=EventTrigger(
        events={NodeDeletedEvent.event_name},
        match=dict(_LIFECYCLE_MATCH),
    ),
    actions=[_lifecycle_action()],
)

TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA = BuiltinTriggerDefinition(
    name="computed-attribute-setup-all",
    trigger=EventTrigger(events={SchemaUpdatedEvent.event_name, BranchDeletedEvent.event_name}),
    actions=[
        ExecuteWorkflow(
            workflow=COMPUTED_ATTRIBUTE_SETUP_JINJA2,
            parameters={
                "branch_name": jinja_parameter("{{ event.resource['infrahub.branch.name'] }}"),
                "event_name": jinja_parameter("{{ event.event }}"),
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
                "changed_elements": {
                    "__prefect_kind": "json",
                    "value": {
                        "__prefect_kind": "jinja",
                        "template": "{{ event.payload['data']['changed_elements'] | default(none, true) | tojson }}",
                    },
                },
            },
        ),
        ExecuteWorkflow(
            workflow=COMPUTED_ATTRIBUTE_SETUP_PYTHON,
            parameters={
                "branch_name": jinja_parameter("{{ event.resource['infrahub.branch.name'] }}"),
                "event_name": jinja_parameter("{{ event.event }}"),
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
                "changed_elements": {
                    "__prefect_kind": "json",
                    "value": {
                        "__prefect_kind": "jinja",
                        "template": "{{ event.payload['data']['changed_elements'] | default(none, true) | tojson }}",
                    },
                },
            },
        ),
    ],
)
