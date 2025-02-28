from infrahub.core.constants import InfrahubKind
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import (
    WEBHOOK_CONFIGURE_ONE,
)

TRIGGER_WEBHOOK_SETUP_UPDATE = BuiltinTriggerDefinition(
    name="webhook-configure-one",
    trigger=EventTrigger(
        events={"infrahub.node.*"},
        match={
            "infrahub.node.kind": [InfrahubKind.CUSTOMWEBHOOK, InfrahubKind.STANDARDWEBHOOK],
        },
    ),
    actions=[
        ExecuteWorkflow(
            workflow=WEBHOOK_CONFIGURE_ONE,
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
