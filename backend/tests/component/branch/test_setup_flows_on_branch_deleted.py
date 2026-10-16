from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.computed_attribute.tasks import computed_attribute_setup_jinja2, computed_attribute_setup_python
from infrahub.context import InfrahubContext
from infrahub.display_labels.tasks import display_labels_setup_jinja2
from infrahub.events.branch_action import BranchDeletedEvent
from infrahub.hfid.tasks import hfid_setup
from infrahub.profiles.tasks import profile_refresh_setup
from infrahub.server import app
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.test_app import TestInfrahubAppWithoutLocalWorkflow
from tests.helpers.workflow_override import override_workflow

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from fast_depends import Provider
    from prefect import State
    from prefect.client.orchestration import PrefectClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.events.models import EventContext
    from infrahub.services import InfrahubServices
    from infrahub.services.adapters.workflow.local import WorkflowLocalExecution

DELETED_BRANCH_NAME = "deleted-branch-setup"


@dataclass
class SetupFlowCase:
    name: str
    flow: Callable[..., Awaitable[State[Any]]]


SETUP_FLOW_CASES = [
    SetupFlowCase(name="hfid_setup", flow=hfid_setup),
    SetupFlowCase(name="display_labels_setup_jinja2", flow=display_labels_setup_jinja2),
    SetupFlowCase(name="profile_refresh_setup", flow=profile_refresh_setup),
    SetupFlowCase(name="computed_attribute_setup_jinja2", flow=computed_attribute_setup_jinja2),
    SetupFlowCase(name="computed_attribute_setup_python", flow=computed_attribute_setup_python),
]


class TestSetupFlowsOnBranchDeleted(TestInfrahubAppWithoutLocalWorkflow):
    @pytest.fixture(scope="class", autouse=True)
    async def service(self, workflow_local: WorkflowLocalExecution, test_client: Any) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self, service: InfrahubServices, dependency_provider: Provider
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        with override_workflow(WorkflowRecorder(), dependency_provider=dependency_provider) as recorder:
            yield recorder

    @staticmethod
    def _context(admin_account: CoreAccount, branch: Branch) -> EventContext:
        account = AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=admin_account.id)
        return InfrahubContext.init(branch=branch, account=account).to_event_context()

    @pytest.mark.parametrize("case", SETUP_FLOW_CASES, ids=[case.name for case in SETUP_FLOW_CASES])
    async def test_setup_flows_do_not_tag_a_deleted_branch(
        self,
        case: SetupFlowCase,
        default_branch: Branch,
        admin_account: CoreAccount,
        prefect_client: PrefectClient,
    ) -> None:
        state = await case.flow(
            context=self._context(admin_account, default_branch),
            branch_name=DELETED_BRANCH_NAME,
            event_name=BranchDeletedEvent.event_name,
            return_state=True,
        )

        assert state.is_completed()
        assert state.state_details.flow_run_id is not None
        flow_run = await prefect_client.read_flow_run(state.state_details.flow_run_id)
        assert flow_run.tags == []
