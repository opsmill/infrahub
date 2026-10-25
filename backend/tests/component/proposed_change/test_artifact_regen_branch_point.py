from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.dependencies.registry import get_component_registry
from infrahub.message_bus.types import ProposedChangeBranchDiff, ProposedChangeRepository
from infrahub.proposed_change.branch_diff import set_diff_summary_cache
from infrahub.proposed_change.models import RequestProposedChangeRefreshArtifacts
from infrahub.proposed_change.tasks import refresh_artifacts, validate_artifacts_generation
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE, REQUEST_ARTIFACT_DEFINITION_CHECK
from tests.helpers.schema import load_schema

from .conftest import QUERY_UNIQUE_TARGETS, ArtifactRegenTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder

REPOSITORY_NAME = "branch-point-repo"
DEFINITION_NAME = "artifact-branch-point"
BRANCH_REBASE = "feature/branch-point-rebase"
BRANCH_DEFAULT_RENDER = "feature/branch-point-default-render"
BRANCH_STORAGE = "feature/branch-point-storage"
DEVICES_BY_BRANCH = {
    BRANCH_REBASE: "dev-rebase",
    BRANCH_DEFAULT_RENDER: "dev-default-render",
    BRANCH_STORAGE: "dev-storage",
}

ARTIFACT_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="NetworkDevice",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            inherit_from=["CoreArtifactTarget"],
            uniqueness_constraints=[["name__value"]],
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="color", kind="Text", optional=True),
                AttributeSchema(name="description", kind="Text", optional=True),
            ],
        )
    ]
)


class TestArtifactRegenBranchPoint(ArtifactRegenTestBase):
    """The artifact checks compare each artifact on the branch with the artifact at the branch point.

    Every device has an artifact rendered on the default branch before the branches are created, and each
    scenario works on its own branch and device.
    """

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch) -> dict[str, Any]:
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, update_db=True)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name=REPOSITORY_NAME, location="https://github.com/test/branch-point-repo.git")
        await repo.save(db=db)

        query = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query.new(db=db, name="GetNetworkDevice", query=QUERY_UNIQUE_TARGETS)
        await query.save(db=db)

        transform = await Node.init(db=db, schema="CoreTransformJinja2")
        await transform.new(
            db=db, name="device-render", query=str(query.id), repository=str(repo.id), template_path="device.j2"
        )
        await transform.save(db=db)

        devices: dict[str, Node] = {}
        for device_name in DEVICES_BY_BRANCH.values():
            device = await Node.init(db=db, schema="TestNetworkDevice")
            await device.new(db=db, name=device_name, color="blue", description="initial")
            await device.save(db=db)
            devices[device_name] = device

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="branch-point-targets", members=list(devices.values()))
        await group.save(db=db)

        artifact_definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artifact_definition.new(
            db=db,
            name=DEFINITION_NAME,
            targets=group,
            transformation=transform,
            content_type="text/plain",
            artifact_name="device-config",
            parameters={"value": {"name": "name__value"}},
        )
        await artifact_definition.save(db=db)

        artifact_ids: dict[str, str] = {}
        for device_name, device in devices.items():
            artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
            await artifact.new(
                db=db,
                name="device-config",
                definition=artifact_definition,
                status="Ready",
                object=device,
                storage_id=f"storage-{device_name}-blue",
                checksum=f"checksum-{device_name}-blue",
                content_type="text/plain",
            )
            await artifact.save(db=db)
            artifact_ids[device_name] = artifact.id

            query_group = await Node.init(db=db, schema="CoreGraphQLQueryGroup")
            await query_group.new(
                db=db, name=f"qg-{device_name}", query=str(query.id), members=[device], subscribers=[artifact]
            )
            await query_group.save(db=db)

        branches: dict[str, Branch] = {}
        proposed_change_ids: dict[str, str] = {}
        for branch_name, device_name in DEVICES_BY_BRANCH.items():
            branches[branch_name] = await create_branch(branch_name=branch_name, db=db)
            await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=branch_name, update_db=False)
            proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
            await proposed_change.new(
                db=db,
                name=f"pc-{device_name}",
                source_branch=branch_name,
                destination_branch=default_branch.name,
            )
            await proposed_change.save(db=db)
            proposed_change_ids[branch_name] = proposed_change.id

        return {
            "repository_id": repo.id,
            "device_ids": {name: device.id for name, device in devices.items()},
            "artifact_ids": artifact_ids,
            "branches": branches,
            "proposed_change_ids": proposed_change_ids,
        }

    async def _set_device(
        self, db: InfrahubDatabase, branch: Branch, device_id: str, color: str, description: str
    ) -> None:
        device = await NodeManager.get_one(db=db, branch=branch, id=device_id)
        device.color.value = color
        device.description.value = description
        await device.save(db=db)

    async def _set_artifact(
        self, db: InfrahubDatabase, branch: Branch, artifact_id: str, checksum: str, storage_id: str
    ) -> None:
        artifact = await NodeManager.get_one(db=db, branch=branch, id=artifact_id)
        artifact.checksum.value = checksum
        artifact.storage_id.value = storage_id
        await artifact.save(db=db)

    async def _run_artifact_checks(
        self,
        *,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        branch_name: str,
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        client: InfrahubClient,
    ) -> tuple[list[str], list[str]]:
        """Run the artifact part of the proposed change pipeline; return the selected definitions and checked targets."""
        workflow_recorder.reset()
        branch = dataset["branches"][branch_name]
        coordinator = await get_component_registry().get_component(DiffCoordinator, db=db, branch=branch)
        await coordinator.update_branch_diff(
            base_branch=default_branch,
            diff_branch=branch,
            proposed_change_id=dataset["proposed_change_ids"][branch_name],
        )

        pipeline_id = uuid.uuid4()
        repository = ProposedChangeRepository(
            repository_id=dataset["repository_id"],
            repository_name=REPOSITORY_NAME,
            read_only=False,
            source_branch=branch_name,
            destination_branch=default_branch.name,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            source_commit="source-commit-sha",
            destination_commit="dest-commit-sha",
        )
        branch_diff = ProposedChangeBranchDiff(pipeline_id=pipeline_id, repositories=[repository])
        await set_diff_summary_cache(
            pipeline_id=pipeline_id,
            diff_summary=await client.get_diff_summary(branch=branch_name),
            cache=memory_cache,
        )
        context = self._make_context(admin_account, default_branch)

        await refresh_artifacts(
            model=RequestProposedChangeRefreshArtifacts(
                proposed_change=dataset["proposed_change_ids"][branch_name],
                source_branch=branch_name,
                source_branch_sync_with_git=False,
                destination_branch=default_branch.name,
                branch_diff=branch_diff,
            ),
            context=context,
        )
        definition_checks = workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
        for call in definition_checks:
            await validate_artifacts_generation(model=call["parameters"]["model"], context=context)

        selected = [call["parameters"]["model"].artifact_definition.definition_name for call in definition_checks]
        checked = [
            call["parameters"]["model"].target_id
            for call in workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        ]
        return selected, checked

    async def test_value_changed_back_before_a_rebase_regenerates_artifact(
        self,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        client: InfrahubClient,
    ) -> None:
        """A rebase drops the changed-back value from the diff, yet the artifact rendered in between is regenerated."""
        branch = dataset["branches"][BRANCH_REBASE]
        device_id = dataset["device_ids"]["dev-rebase"]
        checks = {
            "db": db,
            "dataset": dataset,
            "branch_name": BRANCH_REBASE,
            "default_branch": default_branch,
            "admin_account": admin_account,
            "memory_cache": memory_cache,
            "workflow_recorder": workflow_recorder,
            "client": client,
        }

        await self._set_device(db=db, branch=branch, device_id=device_id, color="red", description="initial")
        assert await self._run_artifact_checks(**checks) == ([DEFINITION_NAME], [device_id])
        await self._set_artifact(
            db=db,
            branch=branch,
            artifact_id=dataset["artifact_ids"]["dev-rebase"],
            checksum="checksum-dev-rebase-red",
            storage_id="storage-dev-rebase-red",
        )
        await self._set_device(db=db, branch=branch, device_id=device_id, color="blue", description="initial")

        await branch.rebase(db=db)
        diff_repository = await get_component_registry().get_component(DiffRepository, db=db, branch=default_branch)
        coordinator = await get_component_registry().get_component(DiffCoordinator, db=db, branch=branch)
        for root in await diff_repository.get_roots_metadata(diff_branch_names=[BRANCH_REBASE]):
            if root.base_branch_name != root.diff_branch_name:
                await coordinator.recalculate(base_branch=default_branch, diff_branch=branch, diff_id=root.uuid)

        assert await self._run_artifact_checks(**checks) == ([DEFINITION_NAME], [device_id])

    async def test_artifact_rendered_again_on_default_branch_after_branch_point_is_not_regenerated(
        self,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        client: InfrahubClient,
    ) -> None:
        """An artifact the branch never rendered is not regenerated because the default branch rendered it again."""
        branch = dataset["branches"][BRANCH_DEFAULT_RENDER]
        await self._set_artifact(
            db=db,
            branch=default_branch,
            artifact_id=dataset["artifact_ids"]["dev-default-render"],
            checksum="checksum-dev-default-render-v2",
            storage_id="storage-dev-default-render-v2",
        )
        # A change to a field the query does not read makes the checks look at the definition's targets.
        await self._set_device(
            db=db,
            branch=branch,
            device_id=dataset["device_ids"]["dev-default-render"],
            color="blue",
            description="edited",
        )

        assert await self._run_artifact_checks(
            db=db,
            dataset=dataset,
            branch_name=BRANCH_DEFAULT_RENDER,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            client=client,
        ) == ([DEFINITION_NAME], [])

    async def test_artifact_with_new_storage_id_and_same_checksum_is_not_regenerated(
        self,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        client: InfrahubClient,
    ) -> None:
        """Content stored again under a new storage id, with the branch point's checksum, is not regenerated."""
        await self._set_artifact(
            db=db,
            branch=dataset["branches"][BRANCH_STORAGE],
            artifact_id=dataset["artifact_ids"]["dev-storage"],
            checksum="checksum-dev-storage-blue",
            storage_id="storage-dev-storage-uploaded-again",
        )

        assert await self._run_artifact_checks(
            db=db,
            dataset=dataset,
            branch_name=BRANCH_STORAGE,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            client=client,
        ) == ([DEFINITION_NAME], [])
