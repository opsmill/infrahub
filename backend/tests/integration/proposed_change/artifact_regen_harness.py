from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import RepositoryInternalStatus
from infrahub.message_bus.types import ProposedChangeBranchDiff, ProposedChangeRepository
from infrahub.proposed_change.branch_diff import set_diff_summary_cache
from infrahub.proposed_change.models import RequestProposedChangeRefreshArtifacts
from infrahub.proposed_change.tasks import refresh_artifacts
from infrahub.workers.dependencies import build_workflow
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_CHECK
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from tests.adapters.cache import MemoryCache


class ArtifactRegenGateHarness(TestInfrahubApp):
    """Drives the real refresh-artifacts selection gate and reports the definitions it dispatches.

    Installs a recording workflow backend over the live one so a scenario can read which
    artifact definitions a repository or node change selects, without running the dispatched
    regeneration. Subclasses build their own dataset (a real imported repository plus the
    artifact definitions under test) exposing ``proposed_change_id``, ``repository_id``,
    ``repository_name`` and ``source_branch``, then call ``_selected_definitions`` per scenario.
    """

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self,
        workflow_local: Any,
        dependency_provider: Provider,
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        # workflow_local scopes build_workflow to the live local backend; depend on it so it runs
        # first, then re-scope to the recorder as the inner (active) provider for refresh_artifacts.
        original = config.OVERRIDE.workflow
        recorder = WorkflowRecorder()
        config.OVERRIDE.workflow = recorder
        with dependency_provider.scope(build_workflow, lambda: recorder):
            yield recorder
        config.OVERRIDE.workflow = original

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorder) -> None:
        workflow_recorder.execute_calls.clear()
        workflow_recorder.submit_calls.clear()

    def _make_context(self, account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=default_branch.name),
            account=AccountSession(account_id=account.id, auth_type=AuthType.API),
        )

    async def _selected_definitions(
        self,
        *,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        diff_summary: list[dict] | None = None,
        files_added: list[str] | None = None,
        files_changed: list[str] | None = None,
        files_removed: list[str] | None = None,
    ) -> list[str]:
        pipeline_id = uuid.uuid4()
        repository = ProposedChangeRepository(
            repository_id=dataset["repository_id"],
            repository_name=dataset["repository_name"],
            read_only=False,
            source_branch=dataset["source_branch"],
            destination_branch=default_branch.name,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            files_added=files_added or [],
            files_changed=files_changed or [],
            files_removed=files_removed or [],
        )
        branch_diff = ProposedChangeBranchDiff(pipeline_id=pipeline_id, repositories=[repository])
        await set_diff_summary_cache(pipeline_id=pipeline_id, diff_summary=diff_summary or [], cache=memory_cache)

        model = RequestProposedChangeRefreshArtifacts(
            proposed_change=dataset["proposed_change_id"],
            source_branch=dataset["source_branch"],
            source_branch_sync_with_git=True,
            destination_branch=default_branch.name,
            branch_diff=branch_diff,
        )
        await refresh_artifacts(model=model, context=self._make_context(admin_account, default_branch))

        return [
            call["parameters"]["model"].artifact_definition.definition_name
            for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
        ]
