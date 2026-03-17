from infrahub.core.constants import InfrahubKind
from infrahub.events.node_action import NodeCreatedEvent, NodeDeletedEvent, NodeUpdatedEvent
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import WEBHOOK_CONFIGURE, WEBHOOK_INVALIDATE_HEADERS

TRIGGER_WEBHOOK_CONFIGURE = BuiltinTriggerDefinition(
    name="webhook-configure",
    trigger=EventTrigger(
        events={NodeCreatedEvent.event_name, NodeUpdatedEvent.event_name, NodeDeletedEvent.event_name},
        match={
            "infrahub.node.kind": [InfrahubKind.CUSTOMWEBHOOK, InfrahubKind.STANDARDWEBHOOK],
        },
    ),
    actions=[
        ExecuteWorkflow(
            workflow=WEBHOOK_CONFIGURE,
            parameters={
                "event_type": "{{ event.event }}",
                "event_data": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['data'] | tojson }}"},
                },
            },
        ),
    ],
)

TRIGGER_KEYVALUE_WEBHOOK_INVALIDATE = BuiltinTriggerDefinition(
    name="webhook-keyvalue-invalidate",
    trigger=EventTrigger(
        events={NodeUpdatedEvent.event_name},
        match={
            "infrahub.node.kind": [
                InfrahubKind.STATICKEYVALUE,
                InfrahubKind.ENVKEYVALUE,
            ],
        },
    ),
    actions=[
        ExecuteWorkflow(
            workflow=WEBHOOK_INVALIDATE_HEADERS,
            parameters={
                "event_type": "{{ event.event }}",
                "event_data": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['data'] | tojson }}"},
                },
            },
        ),
    ],
)
