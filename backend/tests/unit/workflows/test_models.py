from infrahub.workflows.catalogue import BRANCH_REBASE
from infrahub.workflows.constants import WorkflowPriority
from infrahub.workflows.models import WorkflowDefinition, WorkflowParameter


def test_get_parameters() -> None:
    assert BRANCH_REBASE.get_parameters() == {
        "branch": WorkflowParameter(name="branch", type="str", required=True),
        "context": WorkflowParameter(name="context", type="InfrahubContext", required=True),
        "send_events": WorkflowParameter(name="send_events", type="bool", required=False),
    }


def test_default_priority_defaults_to_medium() -> None:
    definition = WorkflowDefinition(name="example-workflow", module="example.module", function="example_flow")
    assert definition.default_priority == WorkflowPriority.MEDIUM


def test_to_deployment_carries_default_work_queue_name() -> None:
    definition = WorkflowDefinition(name="example-workflow", module="example.module", function="example_flow")
    assert definition.to_deployment()["work_queue_name"] == "medium"


def test_to_deployment_carries_explicit_priority_work_queue_name() -> None:
    definition = WorkflowDefinition(
        name="example-workflow",
        module="example.module",
        function="example_flow",
        default_priority=WorkflowPriority.HIGH,
    )
    assert definition.to_deployment()["work_queue_name"] == "high"


def test_to_deployment_cron_carries_schedules_and_work_queue_name() -> None:
    definition = WorkflowDefinition(
        name="example-cron-workflow",
        module="example.module",
        function="example_flow",
        cron="0 3 * * *",
        default_priority=WorkflowPriority.LOW,
    )
    payload = definition.to_deployment()
    assert len(payload["schedules"]) == 1
    assert payload["schedules"][0].schedule.cron == "0 3 * * *"
    assert payload["work_queue_name"] == "low"
