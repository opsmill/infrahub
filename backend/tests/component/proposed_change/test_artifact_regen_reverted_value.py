from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.diff.coordinator import DiffCoordinator
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

SOURCE_BRANCH = "feature/artifact-regen-reverted-value"
REPOSITORY_NAME = "reverted-value-repo"

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
            ],
        )
    ]
)


class TestArtifactRegenRevertedValue(ArtifactRegenTestBase):
    """The proposed change artifact checks regenerate an artifact whose input changed since it was last rendered.

    The artifact and its query group are created on the default branch before the source branch, so the
    branch reads the default branch's artifact until a check renders it again on the branch. The branch
    diff is updated after each change, as the proposed change pipeline does.
    """

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch) -> dict[str, Any]:
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, update_db=True)

        device = await Node.init(db=db, schema="TestNetworkDevice")
        await device.new(db=db, name="dev1", color="blue")
        await device.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name=REPOSITORY_NAME, location="https://github.com/test/reverted-value-repo.git")
        await repo.save(db=db)

        query = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query.new(db=db, name="GetNetworkDevice", query=QUERY_UNIQUE_TARGETS)
        await query.save(db=db)

        transform = await Node.init(db=db, schema="CoreTransformJinja2")
        await transform.new(
            db=db, name="device-render", query=str(query.id), repository=str(repo.id), template_path="device.j2"
        )
        await transform.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="reverted-value-targets", members=[device])
        await group.save(db=db)

        artifact_definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artifact_definition.new(
            db=db,
            name="artifact-reverted-value",
            targets=group,
            transformation=transform,
            content_type="text/plain",
            artifact_name="device-config",
            parameters={"value": {"name": "name__value"}},
        )
        await artifact_definition.save(db=db)

        artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
        await artifact.new(
            db=db,
            name="device-config",
            definition=artifact_definition,
            status="Ready",
            object=device,
            storage_id="storage-rendered-from-blue",
            checksum="checksum-rendered-from-blue",
            content_type="text/plain",
        )
        await artifact.save(db=db)

        query_group = await Node.init(db=db, schema="CoreGraphQLQueryGroup")
        await query_group.new(db=db, name="qg-dev1", query=str(query.id), members=[device], subscribers=[artifact])
        await query_group.save(db=db)

        source_branch = await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db, name="reverted-value-pc", source_branch=SOURCE_BRANCH, destination_branch=default_branch.name
        )
        await proposed_change.save(db=db)

        return {
            "source_branch": source_branch,
            "proposed_change_id": proposed_change.id,
            "repository_id": repo.id,
            "device_id": device.id,
            "artifact_id": artifact.id,
        }

    async def _set_device_color(self, db: InfrahubDatabase, dataset: dict[str, Any], color: str) -> None:
        device = await NodeManager.get_one(db=db, branch=dataset["source_branch"], id=dataset["device_id"])
        device.color.value = color
        await device.save(db=db)

    async def _run_artifact_checks(
        self,
        *,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        client: InfrahubClient,
    ) -> list[str]:
        """Run the artifact part of the proposed change pipeline and return the targets a check was run for."""
        workflow_recorder.reset()
        coordinator = await get_component_registry().get_component(
            DiffCoordinator, db=db, branch=dataset["source_branch"]
        )
        await coordinator.update_branch_diff(
            base_branch=default_branch,
            diff_branch=dataset["source_branch"],
            proposed_change_id=dataset["proposed_change_id"],
        )

        pipeline_id = uuid.uuid4()
        repository = ProposedChangeRepository(
            repository_id=dataset["repository_id"],
            repository_name=REPOSITORY_NAME,
            read_only=False,
            source_branch=SOURCE_BRANCH,
            destination_branch=default_branch.name,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            source_commit="source-commit-sha",
            destination_commit="dest-commit-sha",
        )
        branch_diff = ProposedChangeBranchDiff(pipeline_id=pipeline_id, repositories=[repository])
        await set_diff_summary_cache(
            pipeline_id=pipeline_id,
            diff_summary=await client.get_diff_summary(branch=SOURCE_BRANCH),
            cache=memory_cache,
        )
        context = self._make_context(admin_account, default_branch)

        await refresh_artifacts(
            model=RequestProposedChangeRefreshArtifacts(
                proposed_change=dataset["proposed_change_id"],
                source_branch=SOURCE_BRANCH,
                source_branch_sync_with_git=False,
                destination_branch=default_branch.name,
                branch_diff=branch_diff,
            ),
            context=context,
        )
        for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK):
            await validate_artifacts_generation(model=call["parameters"]["model"], context=context)

        return [
            call["parameters"]["model"].target_id
            for call in workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        ]

    async def test_value_changed_back_to_default_branch_value_regenerates_artifact(
        self,
        db: InfrahubDatabase,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        client: InfrahubClient,
    ) -> None:
        """Changing a value back to the default branch's value regenerates the artifact rendered in between."""
        checks = {
            "db": db,
            "dataset": dataset,
            "default_branch": default_branch,
            "admin_account": admin_account,
            "memory_cache": memory_cache,
            "workflow_recorder": workflow_recorder,
            "client": client,
        }

        await self._set_device_color(db=db, dataset=dataset, color="red")
        assert await self._run_artifact_checks(**checks) == [dataset["device_id"]]

        # The per-target check is only recorded, so write what it stores after rendering from red.
        artifact = await NodeManager.get_one(db=db, branch=dataset["source_branch"], id=dataset["artifact_id"])
        artifact.checksum.value = "checksum-rendered-from-red"
        artifact.storage_id.value = "storage-rendered-from-red"
        await artifact.save(db=db)

        await self._set_device_color(db=db, dataset=dataset, color="blue")

        assert await self._run_artifact_checks(**checks) == [dataset["device_id"]]
