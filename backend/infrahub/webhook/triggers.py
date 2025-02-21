from infrahub.core.constants import InfrahubKind
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import (
    WEBHOOK_CONFIGURE,
)

TRIGGER_WEBHOOK_SETUP_UPDATE = BuiltinTriggerDefinition(
    name="webhook-setup-update-configuration",
    trigger=EventTrigger(
        events={"infrahub.node.*"},
        match={
            "infrahub.node.kind": [InfrahubKind.WEBHOOK, InfrahubKind.STANDARDWEBHOOK],
        },
    ),
    actions=[
        ExecuteWorkflow(
            name=WEBHOOK_CONFIGURE.name,
        ),
    ],
)
