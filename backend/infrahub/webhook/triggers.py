from infrahub.core.constants import InfrahubKind
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import WEBHOOK_CONFIGURE

TRIGGER_WEBHOOK_CONFIGURE = BuiltinTriggerDefinition(
    name="webhook-configure",
    trigger=EventTrigger(
        events={"infrahub.node.created", "infrahub.node.updated", "infrahub.node.deleted"},
        match={
            "infrahub.node.kind": [InfrahubKind.CUSTOMWEBHOOK, InfrahubKind.STANDARDWEBHOOK],
        },
    ),
    actions=[
        ExecuteWorkflow(
            workflow=WEBHOOK_CONFIGURE,
            parameters={
                "event_type": "{{ event.event }}",
                "webhook_id": "{{ event.payload['data']['node_id'] }}",
                "webhook_name": "{{ event.payload['data']['changelog']['display_label'] }}",
                "event_data": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['data'] | tojson }}"},
                },
            },
        ),
    ],
)
