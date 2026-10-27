from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreArtifactCheck, CoreArtifactValidator

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import RepositoryInternalStatus, ValidatorConclusion
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
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
    """Runs the artifact part of a proposed change pipeline, and records checks as the artifact check flow does.

    The per-target artifact check is only recorded by the workflow backend, so a scenario writes what that check
    stores: the rendered artifact on the branch, and the check record linked to the definition's validator.
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

    async def record_check(
        self,
        *,
        branch: Branch,
        proposed_change_id: str,
        definition_id: str,
        artifact_id: str,
        check_name: str,
        checksum: str,
        failed: bool = False,
    ) -> None:
        """Write what the artifact check flow stores after rendering an artifact, or after failing to."""
        if not failed:
            artifact = await NodeManager.get_one(db=self.db, branch=branch, id=artifact_id)
            artifact.checksum.value = checksum
            artifact.storage_id.value = f"storage-{checksum}"
            await artifact.save(db=self.db)

        validators = await self.client.filters(
            kind=CoreArtifactValidator, proposed_change__ids=[proposed_change_id], definition__ids=[definition_id]
        )
        assert len(validators) == 1
        conclusion = ValidatorConclusion.FAILURE if failed else ValidatorConclusion.SUCCESS
        existing = await self.client.filters(
            kind=CoreArtifactCheck, validator__ids=[validators[0].id], name__value=check_name
        )
        if existing:
            check = existing[0]
        else:
            check = await self.client.create(
                kind=CoreArtifactCheck,
                data={
                    "name": check_name,
                    "origin": self.repository_id,
                    "kind": "ArtifactDefinition",
                    "validator": validators[0].id,
                },
            )
        check.created_at.value = Timestamp().to_string()
        check.message.value = "Failed to render artifact" if failed else "Artifact rendered successfully"
        check.conclusion.value = conclusion.value
        check.severity.value = "critical" if failed else "info"
        check.changed.value = not failed
        check.checksum.value = None if failed else checksum
        check.artifact_id.value = artifact_id
        check.storage_id.value = None if failed else f"storage-{checksum}"
        await check.save()


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
