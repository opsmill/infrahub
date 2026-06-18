"""Shared fixtures, helpers, and parametrize case shape for scoped recompute tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncGenerator, ClassVar, Generator

import pytest

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.events.schema_action import ChangedElementsPayload  # noqa: TC001  used in dataclass field
from infrahub.server import app
from infrahub.workers.dependencies import build_workflow
from infrahub.workflows.initialization import setup_task_manager
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.test_app import TestInfrahubAppBase

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.events.models import EventContext
    from infrahub.services import InfrahubServices
    from infrahub.workflows.models import WorkflowDefinition


@dataclass
class ScopedRecomputeCase:
    """A single ``(changed_elements -> expected submitted set)`` parametrize case."""

    name: str
    changed_elements: ChangedElementsPayload | None
    expected_submitted: set[str]


class ScopedRecomputeTestBase(TestInfrahubAppBase):
    """Fixtures and helpers shared by the Jinja2 and Python scoped recompute tests.

    Subclasses set ``WORKFLOW`` to the recompute trigger workflow whose submissions
    are being recorded.
    """

    WORKFLOW: ClassVar[WorkflowDefinition]

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self,
        prefect: Generator[str, None, None],
        dependency_provider: Provider,
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        original = config.OVERRIDE.workflow
        recorder = WorkflowRecorder()
        await setup_task_manager()
        config.OVERRIDE.workflow = recorder
        with dependency_provider.scope(build_workflow, lambda: recorder):
            yield recorder
        config.OVERRIDE.workflow = original

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, test_client: Any) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorder) -> None:
        workflow_recorder.execute_calls.clear()
        workflow_recorder.submit_calls.clear()

    @staticmethod
    def _context(admin_account: CoreAccount, branch: Branch) -> EventContext:
        account = AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=admin_account.id, role="admin")
        return InfrahubContext.init(branch=branch, account=account).to_event_context()

    def _submitted_attribute_names(self, recorder: WorkflowRecorder) -> set[str]:
        return {call["parameters"]["computed_attribute_name"] for call in recorder.get_submit_calls_for(self.WORKFLOW)}
