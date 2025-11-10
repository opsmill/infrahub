from unittest.mock import ANY, AsyncMock, MagicMock, Mock, call, patch
from uuid import uuid4

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import post_process_branch_merge
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffRoot, NameTrackingId
from infrahub.core.diff.models import RequestDiffUpdate
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.component.registry import ComponentDependencyRegistry
from infrahub.generators.constants import GeneratorDefinitionRunSource
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.catalogue import (
    DIFF_UPDATE,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)
from tests.adapters.message_bus import BusRecorder


@pytest.fixture
async def init_service():
    recorder = BusRecorder()
    database = MagicMock()
    workflow = WorkflowLocalExecution()
    service = await InfrahubServices.new(message_bus=recorder, database=database, workflow=workflow)
    return service


@pytest.fixture
def context():
    return InfrahubContext(
        account=AccountSession(account_id="123", auth_type=AuthType.NONE),
        branch=BranchContext(name="main", id="placeholder"),
    )


async def test_merged(default_branch: Branch, prefect_test_fixture, context: InfrahubContext, init_service):
    """
    Test that merge flow triggers corrects events/workflows. It does not actually test these events/workflows behaviors
    as they are mocked.
    """

    source_branch_name = "cr1234"
    target_branch_name = "main"
    right_now = Timestamp()
    tracked_diff_roots = [
        EnrichedDiffRoot(
            base_branch_name=target_branch_name,
            diff_branch_name=str(uuid4()),
            from_time=right_now,
            to_time=right_now,
            uuid=str(uuid4()),
            partner_uuid=str(uuid4()),
            tracking_id=BranchTrackingId(name=str(uuid4())),
        )
        for _ in range(2)
    ]
    untracked_diff_roots = [
        EnrichedDiffRoot(
            base_branch_name=target_branch_name,
            diff_branch_name=str(uuid4()),
            from_time=right_now,
            to_time=right_now,
            uuid=str(uuid4()),
            partner_uuid=str(uuid4()),
            tracking_id=NameTrackingId(name=str(uuid4())),
        )
        for _ in range(2)
    ]
    diff_repo = AsyncMock(spec=DiffRepository)
    diff_repo.get_roots_metadata.return_value = untracked_diff_roots + tracked_diff_roots
    mock_component_registry = Mock(spec=ComponentDependencyRegistry)
    mock_get_component_registry = MagicMock(return_value=mock_component_registry)
    mock_component_registry.get_component.return_value = diff_repo

    with (
        patch("infrahub.core.branch.tasks.get_component_registry", new=mock_get_component_registry),
        patch(
            "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
        ) as mock_submit_workflow,
        patch("infrahub.core.branch.tasks.add_tags"),
        patch("infrahub.core.branch.tasks.get_run_logger"),
    ):
        await post_process_branch_merge.fn(
            source_branch=source_branch_name, target_branch=target_branch_name, context=context
        )

        expected_calls = [
            call(
                workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE,
                parameters={"branch": target_branch_name},
                context=context,
            ),
            call(
                workflow=TRIGGER_GENERATOR_DEFINITION_RUN,
                parameters={"branch": target_branch_name, "source": GeneratorDefinitionRunSource.MERGE},
                context=context,
            ),
            call(
                workflow=DIFF_UPDATE,
                parameters={"model": RequestDiffUpdate(branch_name=tracked_diff_roots[0].diff_branch_name)},
                context=context,
            ),
            call(
                workflow=DIFF_UPDATE,
                parameters={"model": RequestDiffUpdate(branch_name=tracked_diff_roots[1].diff_branch_name)},
                context=context,
            ),
        ]
        mock_submit_workflow.assert_has_calls(expected_calls)
        assert mock_submit_workflow.call_count == len(expected_calls)

    # Use `db=ANY` as a new InfrahubDatabase object is created as we use a new session
    mock_component_registry.get_component.assert_awaited_once_with(DiffRepository, db=ANY, branch=default_branch)
    diff_repo.get_roots_metadata.assert_awaited_once_with(base_branch_names=[target_branch_name])
