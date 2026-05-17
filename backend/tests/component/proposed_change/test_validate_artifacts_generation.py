from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub import config
from infrahub.auth import AccountSession, AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.message_bus.types import (
    ProposedChangeArtifactDefinition,
    ProposedChangeBranchDiff,
    ProposedChangeRepository,
)
from infrahub.proposed_change.branch_diff import set_diff_summary_cache
from infrahub.proposed_change.models import RequestArtifactDefinitionCheck
from infrahub.proposed_change.tasks import _get_subscribers_from_diff, validate_artifacts_generation
from infrahub.server import app
from infrahub.workers.dependencies import build_client, build_workflow
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppBase

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.adapters.cache import MemoryCache
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient

from .conftest import QUERY_NON_UNIQUE_TARGETS, QUERY_UNIQUE_TARGETS, make_node_diff

SOURCE_BRANCH = "feature/artifact-test"

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
                AttributeSchema(name="description", kind="Text", optional=True),
                AttributeSchema(name="color", kind="Text", optional=True),
            ],
        )
    ]
)


class TestValidateArtifactsGeneration(TestInfrahubAppBase):
    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self,
        prefect: Generator[str, None, None],
        dependency_provider: Provider,
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        original = config.OVERRIDE.workflow
        recorder = WorkflowRecorder()
        config.OVERRIDE.workflow = recorder
        with dependency_provider.scope(build_workflow, lambda: recorder):
            yield recorder
        config.OVERRIDE.workflow = original

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, test_client: InfrahubTestClient) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(scope="class")
    async def client(
        self,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        bus_simulator: BusSimulator,
        service: InfrahubServices,
        dependency_provider: Provider,
    ) -> AsyncGenerator[InfrahubClient, None]:
        sdk_config = Config(
            api_token=api_admin_token,
            requester=test_client.async_request,
            sync_requester=test_client.sync_request,
            schema_converge_timeout=5,
        )
        sdk_client = InfrahubClient(config=sdk_config)
        original_client = service._client
        service._client = sdk_client
        with dependency_provider.scope(build_client, lambda: sdk_client):
            yield sdk_client
        service._client = original_client

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorder) -> None:
        workflow_recorder.execute_calls.clear()
        workflow_recorder.submit_calls.clear()

    @pytest.fixture(scope="class")
    async def artifact_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        memory_cache: MemoryCache,
        admin_account: CoreAccount,
    ) -> dict[str, Any]:
        # Load schema for default branch, saved to DB
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, update_db=True)

        # Create all AWARE/AGNOSTIC nodes on the default branch BEFORE creating
        # the source branch, so they are inherited by the branch when it forks.

        # --- Create 4 network devices on default branch ---
        dev1 = await Node.init(db=db, schema="TestNetworkDevice")
        await dev1.new(db=db, name="dev1", color="red", description="Device 1")
        await dev1.save(db=db)

        dev2 = await Node.init(db=db, schema="TestNetworkDevice")
        await dev2.new(db=db, name="dev2", color="blue", description="Device 2")
        await dev2.save(db=db)

        dev3 = await Node.init(db=db, schema="TestNetworkDevice")
        await dev3.new(db=db, name="dev3", color="green", description="Device 3")
        await dev3.save(db=db)

        dev4 = await Node.init(db=db, schema="TestNetworkDevice")
        await dev4.new(db=db, name="dev4", color="yellow", description="Device 4")
        await dev4.save(db=db)

        # --- Repository node (AGNOSTIC) ---
        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(
            db=db,
            name="test-artifact-repo",
            location="https://github.com/test/artifact-repo.git",
        )
        await repo.save(db=db)

        # --- GraphQL query nodes (AWARE) ---
        query_unique = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_unique.new(db=db, name="GetNetworkDevice", query=QUERY_UNIQUE_TARGETS)
        await query_unique.save(db=db)

        query_non_unique = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_non_unique.new(db=db, name="GetAllNetworkDevices", query=QUERY_NON_UNIQUE_TARGETS)
        await query_non_unique.save(db=db)

        # --- Transform (AWARE) ---
        transform = await Node.init(db=db, schema="CoreTransformJinja2")
        await transform.new(
            db=db,
            name="device-render",
            query=str(query_unique.id),
            repository=str(repo.id),
            template_path="device.j2",
        )
        await transform.save(db=db)

        # --- Target group (AWARE) with all 4 devices ---
        targets_group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await targets_group.new(db=db, name="device-targets", members=[dev1, dev2, dev3, dev4])
        await targets_group.save(db=db)

        # --- Artifact definition for artdef_full (AWARE) ---
        artdef_full_node = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef_full_node.new(
            db=db,
            name="artifact-full",
            targets=targets_group,
            transformation=transform,
            content_type="application/json",
            artifact_name="device-config",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef_full_node.save(db=db)

        # --- Artifact definition for artdef_partial (AWARE, same group; only dev1/dev2 will have existing artifacts) ---
        artdef_partial_node = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef_partial_node.new(
            db=db,
            name="artifact-partial",
            targets=targets_group,
            transformation=transform,
            content_type="application/json",
            artifact_name="device-partial-config",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef_partial_node.save(db=db)

        # --- Group + Artifact definition used to exercise an orphan artifact ---
        # The group contains dev1 (kept) so the dispatch loop has something to act on
        # after we skip the orphan row.
        orphan_group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await orphan_group.new(db=db, name="device-targets-orphan", members=[dev1])
        await orphan_group.save(db=db)

        artdef_orphan_node = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef_orphan_node.new(
            db=db,
            name="artifact-orphan",
            targets=orphan_group,
            transformation=transform,
            content_type="application/json",
            artifact_name="device-orphan-config",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef_orphan_node.save(db=db)

        # --- Create source branch AFTER all AWARE nodes are on main ---
        # This ensures the branch inherits them all via the graph branching model.
        source_branch_obj = await create_branch(branch_name=SOURCE_BRANCH, db=db)

        # Propagate schema to source branch registry entry (in-process only, no DB write)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        # --- Artifacts for artdef_full on source_branch (CoreArtifact is LOCAL) ---
        art1 = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=source_branch_obj)
        await art1.new(
            db=db,
            name="device-config",
            definition=artdef_full_node,
            status="Ready",
            object=dev1,
            storage_id=str(uuid.uuid4()),
            checksum="aaaa",
            content_type="application/json",
        )
        await art1.save(db=db)

        art2 = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=source_branch_obj)
        await art2.new(
            db=db,
            name="device-config",
            definition=artdef_full_node,
            status="Ready",
            object=dev2,
            storage_id=str(uuid.uuid4()),
            checksum="bbbb",
            content_type="application/json",
        )
        await art2.save(db=db)

        art3 = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=source_branch_obj)
        await art3.new(
            db=db,
            name="device-config",
            definition=artdef_full_node,
            status="Ready",
            object=dev3,
            storage_id=str(uuid.uuid4()),
            checksum="cccc",
            content_type="application/json",
        )
        await art3.save(db=db)

        art4 = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=source_branch_obj)
        await art4.new(
            db=db,
            name="device-config",
            definition=artdef_full_node,
            status="Ready",
            object=dev4,
            storage_id=str(uuid.uuid4()),
            checksum="dddd",
            content_type="application/json",
        )
        await art4.save(db=db)

        # --- Phantom device + orphan artifact on source_branch ---
        # The phantom device is created so an artifact can be linked to it; once the
        # device is deleted the artifact's `object` relationship is left dangling. This
        # mirrors production rows where a target was removed via a path the artifact
        # cascade does not cover (branch-merge, schema reload, migration, etc.).
        phantom_dev = await Node.init(db=db, schema="TestNetworkDevice", branch=source_branch_obj)
        await phantom_dev.new(db=db, name="phantom", color="grey", description="To be deleted")
        await phantom_dev.save(db=db)

        art_orphan = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=source_branch_obj)
        await art_orphan.new(
            db=db,
            name="device-orphan-config",
            definition=artdef_orphan_node,
            status="Ready",
            object=phantom_dev,
            storage_id=str(uuid.uuid4()),
            checksum="oooo",
            content_type="application/json",
        )
        await art_orphan.save(db=db)

        await phantom_dev.delete(db=db)

        # --- Artifacts for artdef_partial on source_branch (only dev1 and dev2) ---
        art1_p = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=source_branch_obj)
        await art1_p.new(
            db=db,
            name="device-partial-config",
            definition=artdef_partial_node,
            status="Ready",
            object=dev1,
            storage_id=str(uuid.uuid4()),
            checksum="eeee",
            content_type="application/json",
        )
        await art1_p.save(db=db)

        art2_p = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=source_branch_obj)
        await art2_p.new(
            db=db,
            name="device-partial-config",
            definition=artdef_partial_node,
            status="Ready",
            object=dev2,
            storage_id=str(uuid.uuid4()),
            checksum="ffff",
            content_type="application/json",
        )
        await art2_p.save(db=db)

        # --- CoreGraphQLQueryGroups on source_branch for artdef_full ---
        # Each group links one device (member) to its artifact (subscriber)
        qg1 = await Node.init(db=db, schema="CoreGraphQLQueryGroup", branch=source_branch_obj)
        await qg1.new(
            db=db,
            name="qg-dev1-full",
            query=str(query_unique.id),
            members=[dev1],
            subscribers=[art1],
        )
        await qg1.save(db=db)

        qg2 = await Node.init(db=db, schema="CoreGraphQLQueryGroup", branch=source_branch_obj)
        await qg2.new(
            db=db,
            name="qg-dev2-full",
            query=str(query_unique.id),
            members=[dev2],
            subscribers=[art2],
        )
        await qg2.save(db=db)

        qg3 = await Node.init(db=db, schema="CoreGraphQLQueryGroup", branch=source_branch_obj)
        await qg3.new(
            db=db,
            name="qg-dev3-full",
            query=str(query_unique.id),
            members=[dev3],
            subscribers=[art3],
        )
        await qg3.save(db=db)

        qg4 = await Node.init(db=db, schema="CoreGraphQLQueryGroup", branch=source_branch_obj)
        await qg4.new(
            db=db,
            name="qg-dev4-full",
            query=str(query_unique.id),
            members=[dev4],
            subscribers=[art4],
        )
        await qg4.save(db=db)

        # --- CoreGraphQLQueryGroups on source_branch for artdef_partial (dev1 and dev2 only) ---
        qg1_p = await Node.init(db=db, schema="CoreGraphQLQueryGroup", branch=source_branch_obj)
        await qg1_p.new(
            db=db,
            name="qg-dev1-partial",
            query=str(query_unique.id),
            members=[dev1],
            subscribers=[art1_p],
        )
        await qg1_p.save(db=db)

        qg2_p = await Node.init(db=db, schema="CoreGraphQLQueryGroup", branch=source_branch_obj)
        await qg2_p.new(
            db=db,
            name="qg-dev2-partial",
            query=str(query_unique.id),
            members=[dev2],
            subscribers=[art2_p],
        )
        await qg2_p.save(db=db)

        # --- Proposed change node ---
        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(
            db=db,
            name="test-artifact-pc",
            source_branch=SOURCE_BRANCH,
            destination_branch=default_branch.name,
        )
        await pc.save(db=db)

        # --- ProposedChangeRepository (Pydantic model, no DB node needed) ---
        repository = ProposedChangeRepository(
            repository_id=repo.id,
            repository_name="test-artifact-repo",
            read_only=False,
            source_branch=SOURCE_BRANCH,
            destination_branch=default_branch.name,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            source_commit="source-commit-sha",
            destination_commit="dest-commit-sha",
        )

        # --- ProposedChangeArtifactDefinition models (Pydantic, carry query payload) ---
        artdef_full = ProposedChangeArtifactDefinition(
            definition_id=artdef_full_node.id,
            definition_name="artifact-full",
            artifact_name="device-config",
            query_name="GetNetworkDevice",
            query_id=query_unique.id,
            query_models=["TestNetworkDevice"],
            query_payload=QUERY_UNIQUE_TARGETS,
            repository_id=repo.id,
            transform_kind=InfrahubKind.TRANSFORMJINJA2,
            template_path="device.j2",
            content_type="application/json",
            timeout=60,
        )

        artdef_full_non_unique = ProposedChangeArtifactDefinition(
            definition_id=artdef_full_node.id,
            definition_name="artifact-full",
            artifact_name="device-config",
            query_name="GetAllNetworkDevices",
            query_id=query_non_unique.id,
            query_models=["TestNetworkDevice"],
            query_payload=QUERY_NON_UNIQUE_TARGETS,
            repository_id=repo.id,
            transform_kind=InfrahubKind.TRANSFORMJINJA2,
            template_path="device.j2",
            content_type="application/json",
            timeout=60,
        )

        artdef_partial = ProposedChangeArtifactDefinition(
            definition_id=artdef_partial_node.id,
            definition_name="artifact-partial",
            artifact_name="device-partial-config",
            query_name="GetNetworkDevice",
            query_id=query_unique.id,
            query_models=["TestNetworkDevice"],
            query_payload=QUERY_UNIQUE_TARGETS,
            repository_id=repo.id,
            transform_kind=InfrahubKind.TRANSFORMJINJA2,
            template_path="device.j2",
            content_type="application/json",
            timeout=60,
        )

        artdef_orphan = ProposedChangeArtifactDefinition(
            definition_id=artdef_orphan_node.id,
            definition_name="artifact-orphan",
            artifact_name="device-orphan-config",
            query_name="GetNetworkDevice",
            query_id=query_unique.id,
            query_models=["TestNetworkDevice"],
            query_payload=QUERY_UNIQUE_TARGETS,
            repository_id=repo.id,
            transform_kind=InfrahubKind.TRANSFORMJINJA2,
            template_path="device.j2",
            content_type="application/json",
            timeout=60,
        )

        return {
            "source_branch": SOURCE_BRANCH,
            "proposed_change_id": pc.id,
            "dev1_id": dev1.id,
            "dev2_id": dev2.id,
            "dev3_id": dev3.id,
            "dev4_id": dev4.id,
            "art1_id": art1.id,
            "art2_id": art2.id,
            "art3_id": art3.id,
            "art4_id": art4.id,
            "art1_p_id": art1_p.id,
            "art2_p_id": art2_p.id,
            "repository": repository,
            "artdef_full": artdef_full,
            "artdef_full_non_unique": artdef_full_non_unique,
            "artdef_partial": artdef_partial,
            "artdef_orphan": artdef_orphan,
            "art_orphan_id": art_orphan.id,
        }

    def _make_context(self, account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=default_branch.name),
            account=AccountSession(account_id=account.id, auth_type=AuthType.API),
        )

    async def _make_branch_diff(
        self,
        dataset: dict[str, Any],
        pipeline_id: uuid.UUID,
        diff_summary: list[dict],
        client: InfrahubClient,
        files_changed: list[str] | None = None,
    ) -> ProposedChangeBranchDiff:
        repository = dataset["repository"]
        if files_changed:
            repository = ProposedChangeRepository(
                repository_id=repository.repository_id,
                repository_name=repository.repository_name,
                read_only=repository.read_only,
                source_branch=repository.source_branch,
                destination_branch=repository.destination_branch,
                internal_status=repository.internal_status,
                source_commit=repository.source_commit,
                destination_commit=repository.destination_commit,
                files_changed=files_changed,
            )
        subscribers = await _get_subscribers_from_diff(diff_summary=diff_summary, branch=SOURCE_BRANCH, client=client)
        return ProposedChangeBranchDiff(
            pipeline_id=pipeline_id,
            repositories=[repository],
            subscribers=subscribers,
        )

    async def _run(
        self,
        model: RequestArtifactDefinitionCheck,
        context: InfrahubContext,
        diff_summary: list[dict],
        memory_cache: MemoryCache,
    ) -> None:
        await set_diff_summary_cache(
            pipeline_id=model.branch_diff.pipeline_id,
            diff_summary=diff_summary,
            cache=memory_cache,
        )
        await validate_artifacts_generation(model=model, context=context)

    async def test_unique_query_selective_field_change(
        self,
        artifact_dataset: dict[str, Any],
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """Unique query: dev1 and dev3 change 'name' (queried), dev2 changes 'description' (not queried).

        Only art1 and art3 should be regenerated.
        """
        pipeline_id = uuid.uuid4()
        context = self._make_context(admin_account, default_branch)
        diff_summary = [
            make_node_diff(artifact_dataset["dev1_id"], "TestNetworkDevice", SOURCE_BRANCH, ["name"]),
            make_node_diff(artifact_dataset["dev2_id"], "TestNetworkDevice", SOURCE_BRANCH, ["description"]),
            make_node_diff(artifact_dataset["dev3_id"], "TestNetworkDevice", SOURCE_BRANCH, ["name"]),
        ]
        branch_diff = await self._make_branch_diff(
            artifact_dataset, pipeline_id, diff_summary=diff_summary, client=client
        )

        model = RequestArtifactDefinitionCheck(
            artifact_definition=artifact_dataset["artdef_full"],
            branch_diff=branch_diff,
            proposed_change=artifact_dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=False,
            destination_branch=default_branch.name,
        )

        await self._run(model=model, context=context, diff_summary=diff_summary, memory_cache=memory_cache)

        triggered_ids = {c["parameters"]["model"].target_id for c in workflow_recorder.execute_calls}
        assert triggered_ids == {artifact_dataset["dev1_id"], artifact_dataset["dev3_id"]}

    async def test_unique_query_only_non_queried_field_changes(
        self,
        artifact_dataset: dict[str, Any],
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """Unique query: all devices change 'description' (not queried).

        No artifacts should be regenerated.
        """
        pipeline_id = uuid.uuid4()
        context = self._make_context(admin_account, default_branch)
        diff_summary = [
            make_node_diff(artifact_dataset["dev1_id"], "TestNetworkDevice", SOURCE_BRANCH, ["description"]),
            make_node_diff(artifact_dataset["dev2_id"], "TestNetworkDevice", SOURCE_BRANCH, ["description"]),
            make_node_diff(artifact_dataset["dev3_id"], "TestNetworkDevice", SOURCE_BRANCH, ["description"]),
            make_node_diff(artifact_dataset["dev4_id"], "TestNetworkDevice", SOURCE_BRANCH, ["description"]),
        ]
        branch_diff = await self._make_branch_diff(
            artifact_dataset, pipeline_id, diff_summary=diff_summary, client=client
        )

        model = RequestArtifactDefinitionCheck(
            artifact_definition=artifact_dataset["artdef_full"],
            branch_diff=branch_diff,
            proposed_change=artifact_dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=False,
            destination_branch=default_branch.name,
        )

        await self._run(model=model, context=context, diff_summary=diff_summary, memory_cache=memory_cache)

        assert workflow_recorder.execute_calls == []

    async def test_unique_query_all_queried_field_changes(
        self,
        artifact_dataset: dict[str, Any],
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """Unique query: all 4 devices change 'name' (queried).

        All 4 artifacts should be regenerated.
        """
        pipeline_id = uuid.uuid4()
        context = self._make_context(admin_account, default_branch)
        diff_summary = [
            make_node_diff(artifact_dataset["dev1_id"], "TestNetworkDevice", SOURCE_BRANCH, ["name"]),
            make_node_diff(artifact_dataset["dev2_id"], "TestNetworkDevice", SOURCE_BRANCH, ["name"]),
            make_node_diff(artifact_dataset["dev3_id"], "TestNetworkDevice", SOURCE_BRANCH, ["name"]),
            make_node_diff(artifact_dataset["dev4_id"], "TestNetworkDevice", SOURCE_BRANCH, ["name"]),
        ]
        branch_diff = await self._make_branch_diff(
            artifact_dataset, pipeline_id, diff_summary=diff_summary, client=client
        )

        model = RequestArtifactDefinitionCheck(
            artifact_definition=artifact_dataset["artdef_full"],
            branch_diff=branch_diff,
            proposed_change=artifact_dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=False,
            destination_branch=default_branch.name,
        )

        await self._run(model=model, context=context, diff_summary=diff_summary, memory_cache=memory_cache)

        triggered_ids = {c["parameters"]["model"].target_id for c in workflow_recorder.execute_calls}
        assert triggered_ids == {
            artifact_dataset["dev1_id"],
            artifact_dataset["dev2_id"],
            artifact_dataset["dev3_id"],
            artifact_dataset["dev4_id"],
        }

    async def test_unique_query_new_targets_always_regenerate(
        self,
        artifact_dataset: dict[str, Any],
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """Unique query with artdef_partial: dev3 changes 'description' (not queried).

        dev1 and dev2 have existing artifacts that are not impacted.
        dev3 and dev4 have no existing artifacts (artifact_id=None) → always regenerated.
        """
        pipeline_id = uuid.uuid4()
        context = self._make_context(admin_account, default_branch)
        diff_summary = [
            make_node_diff(artifact_dataset["dev3_id"], "TestNetworkDevice", SOURCE_BRANCH, ["description"]),
        ]
        branch_diff = await self._make_branch_diff(
            artifact_dataset, pipeline_id, diff_summary=diff_summary, client=client
        )

        model = RequestArtifactDefinitionCheck(
            artifact_definition=artifact_dataset["artdef_partial"],
            branch_diff=branch_diff,
            proposed_change=artifact_dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=False,
            destination_branch=default_branch.name,
        )

        await self._run(model=model, context=context, diff_summary=diff_summary, memory_cache=memory_cache)

        triggered_ids = {c["parameters"]["model"].target_id for c in workflow_recorder.execute_calls}
        assert triggered_ids == {artifact_dataset["dev3_id"], artifact_dataset["dev4_id"]}

    async def test_non_unique_query_non_queried_field_change_skips_regeneration(
        self,
        artifact_dataset: dict[str, Any],
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """Non-unique query: only 'description' (not queried) changes.

        Even though the query can't target specific nodes, the queried fields
        haven't changed so no regeneration is needed.
        """
        pipeline_id = uuid.uuid4()
        context = self._make_context(admin_account, default_branch)
        diff_summary = [
            make_node_diff(artifact_dataset["dev1_id"], "TestNetworkDevice", SOURCE_BRANCH, ["description"]),
            make_node_diff(artifact_dataset["dev2_id"], "TestNetworkDevice", SOURCE_BRANCH, ["description"]),
        ]
        branch_diff = await self._make_branch_diff(
            artifact_dataset, pipeline_id, diff_summary=diff_summary, client=client
        )

        model = RequestArtifactDefinitionCheck(
            artifact_definition=artifact_dataset["artdef_full_non_unique"],
            branch_diff=branch_diff,
            proposed_change=artifact_dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=False,
            destination_branch=default_branch.name,
        )

        await self._run(model=model, context=context, diff_summary=diff_summary, memory_cache=memory_cache)

        assert workflow_recorder.execute_calls == []

    async def test_non_unique_query_queried_field_change_regenerates_all(
        self,
        artifact_dataset: dict[str, Any],
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """Non-unique query: dev2 changes 'name' (queried).

        Because the query cannot identify specific targets, all 4 artifacts must be regenerated.
        """
        pipeline_id = uuid.uuid4()
        context = self._make_context(admin_account, default_branch)
        diff_summary = [
            make_node_diff(artifact_dataset["dev2_id"], "TestNetworkDevice", SOURCE_BRANCH, ["name"]),
        ]
        branch_diff = await self._make_branch_diff(
            artifact_dataset, pipeline_id, diff_summary=diff_summary, client=client
        )

        model = RequestArtifactDefinitionCheck(
            artifact_definition=artifact_dataset["artdef_full_non_unique"],
            branch_diff=branch_diff,
            proposed_change=artifact_dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=False,
            destination_branch=default_branch.name,
        )

        await self._run(model=model, context=context, diff_summary=diff_summary, memory_cache=memory_cache)

        triggered_ids = {c["parameters"]["model"].target_id for c in workflow_recorder.execute_calls}
        assert triggered_ids == {
            artifact_dataset["dev1_id"],
            artifact_dataset["dev2_id"],
            artifact_dataset["dev3_id"],
            artifact_dataset["dev4_id"],
        }

    async def test_managed_branch_with_file_changes_regenerates_all(
        self,
        artifact_dataset: dict[str, Any],
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """When source branch is synced with git and the repository has file changes,.

        all artifacts must be regenerated regardless of which fields changed.

        """
        pipeline_id = uuid.uuid4()
        context = self._make_context(admin_account, default_branch)
        # Only description changed (not queried) — but managed_branch=True overrides this
        diff_summary = [
            make_node_diff(artifact_dataset["dev1_id"], "TestNetworkDevice", SOURCE_BRANCH, ["description"]),
        ]
        branch_diff = await self._make_branch_diff(
            artifact_dataset,
            pipeline_id,
            diff_summary=diff_summary,
            client=client,
            files_changed=["templates/device.j2"],
        )

        model = RequestArtifactDefinitionCheck(
            artifact_definition=artifact_dataset["artdef_full"],
            branch_diff=branch_diff,
            proposed_change=artifact_dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=True,
            destination_branch=default_branch.name,
        )

        await self._run(model=model, context=context, diff_summary=diff_summary, memory_cache=memory_cache)

        triggered_ids = {c["parameters"]["model"].target_id for c in workflow_recorder.execute_calls}
        assert triggered_ids == {
            artifact_dataset["dev1_id"],
            artifact_dataset["dev2_id"],
            artifact_dataset["dev3_id"],
            artifact_dataset["dev4_id"],
        }

    async def test_orphan_artifact_does_not_block_dispatch(
        self,
        artifact_dataset: dict[str, Any],
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """An artifact whose `object` peer can no longer be resolved must not.

        prevent the validator from dispatching artifact creation for the rest of
        the group. dev1 is a member of the orphan group with no existing artifact
        for that definition, so it should always be regenerated.

        """
        pipeline_id = uuid.uuid4()
        context = self._make_context(admin_account, default_branch)
        diff_summary: list[dict] = []
        branch_diff = await self._make_branch_diff(
            artifact_dataset, pipeline_id, diff_summary=diff_summary, client=client
        )

        model = RequestArtifactDefinitionCheck(
            artifact_definition=artifact_dataset["artdef_orphan"],
            branch_diff=branch_diff,
            proposed_change=artifact_dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=False,
            destination_branch=default_branch.name,
        )

        await self._run(model=model, context=context, diff_summary=diff_summary, memory_cache=memory_cache)

        triggered_ids = {c["parameters"]["model"].target_id for c in workflow_recorder.execute_calls}
        assert triggered_ids == {artifact_dataset["dev1_id"]}

    async def test_managed_branch_without_file_changes_uses_field_targeting(
        self,
        artifact_dataset: dict[str, Any],
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """When source branch is synced with git but no file changes, field-level targeting.

        still applies. Only the artifact for dev1 (name changed) should be regenerated.

        """
        pipeline_id = uuid.uuid4()
        context = self._make_context(admin_account, default_branch)
        # No files_changed → has_file_modifications=False → managed_branch=False
        diff_summary = [
            make_node_diff(artifact_dataset["dev1_id"], "TestNetworkDevice", SOURCE_BRANCH, ["name"]),
        ]
        branch_diff = await self._make_branch_diff(
            artifact_dataset, pipeline_id, diff_summary=diff_summary, client=client
        )

        model = RequestArtifactDefinitionCheck(
            artifact_definition=artifact_dataset["artdef_full"],
            branch_diff=branch_diff,
            proposed_change=artifact_dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=True,
            destination_branch=default_branch.name,
        )

        await self._run(model=model, context=context, diff_summary=diff_summary, memory_cache=memory_cache)

        triggered_ids = {c["parameters"]["model"].target_id for c in workflow_recorder.execute_calls}
        assert triggered_ids == {artifact_dataset["dev1_id"]}
