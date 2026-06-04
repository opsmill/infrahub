from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.message_bus.types import ProposedChangeBranchDiff, ProposedChangeRepository
from infrahub.proposed_change.branch_diff import set_diff_summary_cache
from infrahub.proposed_change.models import RequestProposedChangeRefreshArtifacts
from infrahub.proposed_change.tasks import refresh_artifacts
from infrahub.server import app
from infrahub.workers.dependencies import build_client, build_workflow
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_CHECK
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppBase

from .conftest import make_node_diff

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

SOURCE_BRANCH = "feature/artifact-regen-edge-cases"

QUERY = """
query GetDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } } }
    }
}
"""

ARTIFACT_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="NetworkDevice",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            inherit_from=["CoreArtifactTarget"],
            uniqueness_constraints=[["name__value"]],
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        )
    ]
)


class TestArtifactRegenEdgeCases(TestInfrahubAppBase):
    """Boundary behaviors of the selection gate not expressible at the unit level.

    Covers net-empty diffs, whole-repo manifest edits, single-dispatch deduplication,
    shared queries, and source-branch-only definitions.

    Each scenario drives ``refresh_artifacts`` and inspects which definitions are
    dispatched for regeneration, covering cases that the per-predicate unit tests
    cannot express because they depend on the gate iterating over several real
    definitions backed by a shared repository.
    """

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
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, update_db=True)

        device = await Node.init(db=db, schema="TestNetworkDevice")
        await device.new(db=db, name="dev1")
        await device.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name="edge-repo", location="https://github.com/test/edge-repo.git")
        await repo.save(db=db)

        query_solo = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_solo.new(db=db, name="GetDeviceSolo", query=QUERY)
        await query_solo.save(db=db)

        query_shared = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_shared.new(db=db, name="GetDeviceShared", query=QUERY)
        await query_shared.save(db=db)

        query_new = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_new.new(db=db, name="GetDeviceNew", query=QUERY)
        await query_new.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="edge-targets", members=[device])
        await group.save(db=db)

        async def _make_definition(
            *, def_name: str, artifact_name: str, query_id: str, template: str, branch: Branch | None = None
        ) -> Node:
            transform = await Node.init(db=db, schema="CoreTransformJinja2", branch=branch)
            await transform.new(
                db=db,
                name=f"transform-{def_name}",
                query=query_id,
                repository=str(repo.id),
                template_path=template,
                dependencies=[".infrahub.yml", template],
                dependencies_complete=True,
            )
            await transform.save(db=db)

            definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION, branch=branch)
            await definition.new(
                db=db,
                name=def_name,
                targets=group,
                transformation=transform,
                content_type="text/plain",
                artifact_name=artifact_name,
                parameters={"value": {"name": "name__value"}},
            )
            await definition.save(db=db)
            return definition

        artdef_a = await _make_definition(
            def_name="artifact-a", artifact_name="device-a", query_id=str(query_solo.id), template="templates/a.j2"
        )
        artdef_s1 = await _make_definition(
            def_name="artifact-s1", artifact_name="device-s1", query_id=str(query_shared.id), template="templates/s1.j2"
        )
        artdef_s2 = await _make_definition(
            def_name="artifact-s2", artifact_name="device-s2", query_id=str(query_shared.id), template="templates/s2.j2"
        )

        source_branch = await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        # A definition that exists only on the source branch; it has no counterpart on
        # the destination branch, so it surfaces as an "added" node in the diff.
        artdef_new = await _make_definition(
            def_name="artifact-new",
            artifact_name="device-new",
            query_id=str(query_new.id),
            template="templates/new.j2",
            branch=source_branch,
        )

        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(db=db, name="regen-edge-pc", source_branch=SOURCE_BRANCH, destination_branch=default_branch.name)
        await pc.save(db=db)

        return {
            "proposed_change_id": pc.id,
            "repository_id": repo.id,
            "query_shared_id": query_shared.id,
            "query_solo_id": query_solo.id,
            "artdef_a_id": artdef_a.id,
            "artdef_s1_id": artdef_s1.id,
            "artdef_s2_id": artdef_s2.id,
            "artdef_new_id": artdef_new.id,
        }

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
        diff_summary: list[dict],
        files_changed: list[str] | None = None,
    ) -> list[str]:
        pipeline_id = uuid.uuid4()
        repository = ProposedChangeRepository(
            repository_id=dataset["repository_id"],
            repository_name="edge-repo",
            read_only=False,
            source_branch=SOURCE_BRANCH,
            destination_branch=default_branch.name,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            files_changed=files_changed or [],
        )
        branch_diff = ProposedChangeBranchDiff(pipeline_id=pipeline_id, repositories=[repository])
        await set_diff_summary_cache(pipeline_id=pipeline_id, diff_summary=diff_summary, cache=memory_cache)

        model = RequestProposedChangeRefreshArtifacts(
            proposed_change=dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=True,
            destination_branch=default_branch.name,
            branch_diff=branch_diff,
        )
        await refresh_artifacts(model=model, context=self._make_context(admin_account, default_branch))

        return [
            call["parameters"]["model"].artifact_definition.definition_name
            for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
        ]

    async def test_net_empty_diff_regenerates_nothing(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """An edit reverted within the same branch leaves no net change, so nothing regenerates."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[],
            files_changed=[],
        )
        assert selected == []

    async def test_manifest_edit_regenerates_every_transform_in_repo(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """Editing ``.infrahub.yml`` regenerates every transform because it is in each closure.

        The manifest is appended to every transform's dependency list at import time, so
        a manifest change conservatively selects all definitions backed by the repository.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[],
            files_changed=[".infrahub.yml"],
        )
        assert set(selected) == {"artifact-a", "artifact-s1", "artifact-s2", "artifact-new"}

    async def test_query_and_transform_change_dispatches_definition_once(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A definition whose query and transform both change is dispatched exactly once."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[make_node_diff(dataset["query_solo_id"], "CoreGraphQLQuery", SOURCE_BRANCH, ["query"])],
            files_changed=["templates/a.j2"],
        )
        assert selected == ["artifact-a"]

    async def test_shared_query_edit_selects_every_dependent_definition(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A query edit selects every definition whose transform references that query."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[make_node_diff(dataset["query_shared_id"], "CoreGraphQLQuery", SOURCE_BRANCH, ["query"])],
        )
        assert set(selected) == {"artifact-s1", "artifact-s2"}

    async def test_source_branch_only_definition_is_selected(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A definition that exists only on the source branch is selected as an added node.

        The gather query reads the source branch, so a source-only definition appears in
        the candidate set and its diff entry carries the ``added`` action that the
        definition predicate fires on.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[
                make_node_diff(
                    dataset["artdef_new_id"], "CoreArtifactDefinition", SOURCE_BRANCH, ["name"], action="added"
                )
            ],
        )
        assert selected == ["artifact-new"]
