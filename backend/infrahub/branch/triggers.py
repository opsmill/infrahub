from infrahub.events.branch_action import BranchMergedEvent
from infrahub.trigger.models import BuiltinTriggerDefinition, EventTrigger, ExecuteWorkflow
from infrahub.workflows.catalogue import BRANCH_MERGED

TRIGGER_BRANCH_MERGED = BuiltinTriggerDefinition(
    name="branch-merged-trigger",
    trigger=EventTrigger(
        events={BranchMergedEvent.event_name},
    ),
    actions=[
        ExecuteWorkflow(
            workflow=BRANCH_MERGED,
            parameters={
                "source_branch": "{{ event.payload['data']['branch_name'] }}",
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
            },
        ),
    ],
)
