from infrahub.workflows.catalogue import BRANCH_REBASE
from infrahub.workflows.models import WorkflowParameter


def test_get_parameters():
    assert BRANCH_REBASE.get_parameters() == {
        "branch": WorkflowParameter(name="branch", type="str", required=True),
        "context": WorkflowParameter(name="context", type="InfrahubContext", required=True),
        "send_events": WorkflowParameter(name="send_events", type="bool", required=False),
    }
