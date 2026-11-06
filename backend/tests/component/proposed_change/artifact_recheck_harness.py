from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.artifacts.query_data import RenderedQueryData, fingerprint_query_data
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import RepositoryInternalStatus
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.manager import NodeManager
from infrahub.dependencies.registry import get_component_registry
from infrahub.message_bus.types import ProposedChangeBranchDiff, ProposedChangeRepository
from infrahub.proposed_change.branch_diff import set_diff_summary_cache
from infrahub.proposed_change.models import RequestProposedChangeRefreshArtifacts
from infrahub.proposed_change.tasks import refresh_artifacts, validate_artifacts_generation
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE, REQUEST_ARTIFACT_DEFINITION_CHECK

from .conftest import ArtifactRegenTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder


@dataclass
class ArtifactPipeline:
    """Runs the artifact part of a proposed change pipeline, and records renderings as the render step does.

    The per-target artifact check is only recorded by the workflow backend, so a scenario writes what rendering
    stores: the rendered artifact on the branch, and the fingerprint of the query data it was rendered from.
    """

    db: InfrahubDatabase
    client: InfrahubClient
    default_branch: Branch
    admin_account: CoreAccount
    memory_cache: MemoryCache
    workflow_recorder: WorkflowRecorder
    repository_id: str

    async def run_checks(self, *, branch: Branch, proposed_change_id: str) -> tuple[list[str], list[str]]:
        """Return the definitions selected for checking and the sorted ids of the targets checked."""
        self.workflow_recorder.reset()
        coordinator = await get_component_registry().get_component(DiffCoordinator, db=self.db, branch=branch)
        await coordinator.update_branch_diff(
            base_branch=self.default_branch, diff_branch=branch, proposed_change_id=proposed_change_id
        )

        pipeline_id = uuid.uuid4()
        repository = ProposedChangeRepository(
            repository_id=self.repository_id,
            repository_name="recheck-repo",
            read_only=False,
            source_branch=branch.name,
            destination_branch=self.default_branch.name,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            source_commit="source-commit-sha",
            destination_commit="dest-commit-sha",
        )
        branch_diff = ProposedChangeBranchDiff(pipeline_id=pipeline_id, repositories=[repository])
        await set_diff_summary_cache(
            pipeline_id=pipeline_id,
            diff_summary=await self.client.get_diff_summary(branch=branch.name),
            cache=self.memory_cache,
        )
        context = InfrahubContext(
            branch=BranchContext(name=self.default_branch.name),
            account=AccountSession(account_id=self.admin_account.id, auth_type=AuthType.API),
        )

        await refresh_artifacts(
            model=RequestProposedChangeRefreshArtifacts(
                proposed_change=proposed_change_id,
                source_branch=branch.name,
                source_branch_sync_with_git=False,
                destination_branch=self.default_branch.name,
                branch_diff=branch_diff,
            ),
            context=context,
        )
        definition_checks = self.workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
        for call in definition_checks:
            await validate_artifacts_generation(model=call["parameters"]["model"], context=context)

        selected = [call["parameters"]["model"].artifact_definition.definition_name for call in definition_checks]
        checked = sorted(
            call["parameters"]["model"].target_id
            for call in self.workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        )
        return selected, checked

    async def record_render(
        self,
        *,
        branch: Branch,
        artifact_id: str,
        query_id: str,
        variables: dict[str, str],
        checksum: str,
        failed: bool = False,
    ) -> None:
        """Write what rendering an artifact on the branch stores, or what a failed rendering leaves behind."""
        artifact = await NodeManager.get_one(db=self.db, branch=branch, id=artifact_id)
        rendered_query_data = RenderedQueryData(cache=self.memory_cache)
        branch_id = str(branch.get_uuid())
        if failed:
            artifact.status.value = "Error"
            await artifact.save(db=self.db)
            await rendered_query_data.forget(branch_id=branch_id, artifact_id=artifact_id)
            return

        artifact.checksum.value = checksum
        artifact.storage_id.value = f"storage-{checksum}"
        await artifact.save(db=self.db)
        response = await self.client.query_gql_query(name=query_id, variables=variables, branch_name=branch.name)
        await rendered_query_data.save(
            branch_id=branch_id, artifact_id=artifact_id, fingerprint=fingerprint_query_data(response)
        )


class ArtifactRecheckTestBase(ArtifactRegenTestBase):
    """Exposes an ``ArtifactPipeline`` bound to the scenario's dataset."""

    @pytest.fixture
    def pipeline(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        dataset: dict[str, object],
    ) -> ArtifactPipeline:
        repository_id = dataset["repository_id"]
        assert isinstance(repository_id, str)
        return ArtifactPipeline(
            db=db,
            client=client,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            repository_id=repository_id,
        )
