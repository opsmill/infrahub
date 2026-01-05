from infrahub.events.node_action import NodeCreatedEvent, NodeDeletedEvent, NodeUpdatedEvent
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import CONFIGURE_ACTION_RULES

from .constants import NODES_THAT_TRIGGER_ACTION_RULES_SETUP

TRIGGER_ACTION_RULE_UPDATE = BuiltinTriggerDefinition(
    name="action-trigger-setup-all",
    trigger=EventTrigger(
        events={NodeCreatedEvent.event_name, NodeDeletedEvent.event_name, NodeUpdatedEvent.event_name},
        match={
            "infrahub.node.kind": NODES_THAT_TRIGGER_ACTION_RULES_SETUP,
        },
    ),
    actions=[
        ExecuteWorkflow(
            workflow=CONFIGURE_ACTION_RULES,
            parameters={},
        ),
    ],
)
