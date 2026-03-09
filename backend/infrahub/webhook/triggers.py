from infrahub.core.constants import InfrahubKind
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import WEBHOOK_CONFIGURE

TRIGGER_WEBHOOK_SETUP_UPDATE = BuiltinTriggerDefinition(
    name="webhook-configure-one",
    trigger=EventTrigger(
        events={"infrahub.node.created", "infrahub.node.updated"},
        match={
            "infrahub.node.kind": [InfrahubKind.CUSTOMWEBHOOK, InfrahubKind.STANDARDWEBHOOK],
        },
    ),
    actions=[
        ExecuteWorkflow(
            workflow=WEBHOOK_CONFIGURE,
            parameters={
                "action": "configure",
                "webhook_name": "{{ event.payload['data']['changelog']['display_label'] }}",
                "event_data": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['data'] | tojson }}"},
                },
            },
        ),
    ],
)

TRIGGER_WEBHOOK_DELETE = BuiltinTriggerDefinition(
    name="webhook-delete",
    trigger=EventTrigger(
        events={"infrahub.node.deleted"},
        match={
            "infrahub.node.kind": [InfrahubKind.CUSTOMWEBHOOK, InfrahubKind.STANDARDWEBHOOK],
        },
    ),
    actions=[
        ExecuteWorkflow(
            workflow=WEBHOOK_CONFIGURE,
            parameters={
                "action": "delete",
                "webhook_id": "{{ event.payload['data']['node_id'] }}",
                "webhook_name": "{{ event.payload['data']['changelog']['display_label'] }}",
            },
        ),
    ],
)
