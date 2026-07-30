from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.diff.summary_cache import DiffSummaryCache
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.initialization import create_branch
from infrahub.core.merge.regeneration_dispatcher import PostMergeRegenerationDispatcher
from infrahub.core.merge.selective_regen.generator_output import GeneratorCascadeOutput
from infrahub.core.merge.selective_regen.orchestrator import build_merge_selective_regeneration
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.server import app
from infrahub.workers.dependencies import build_client, build_workflow
from infrahub.workflows.catalogue import (
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_GENERATOR_DEFINITION_RUN,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
)
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppBase

from .conftest import make_node_diff

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from fast_depends import Provider
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.adapters.cache import MemoryCache
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient


class _StubGeneratorDiffCapturer:
    """Return a canned diff summary standing in for an after-merge generator's writes.

    The dispatch-level tests record generator runs rather than executing them, so no real writes land
    to capture; this feeds the selector the diff a generator's output would have produced.
    """

    def __init__(self, diff_summary: list[NodeDiff]) -> None:
        self._diff_summary = diff_summary
        self.calls = 0

    async def capture(self, *, since: Timestamp, generator_definition_names: list[str]) -> list[NodeDiff]:
        self.calls += 1
        return self._diff_summary


SOURCE_BRANCH = "feature/merge-selective-regen"
DIFF_CACHE_KEY = "merge-selective-diff"

SELECTIVE_SCHEMA = SchemaRoot(
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

DEVICE_QUERY = """
query GetDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } } }
    }
}
"""


class TestMergeSelectiveRegenSelection(TestInfrahubAppBase):
    """The post-merge dispatcher selects only the definitions a merge diff touches, against a live graph.

    Drives ``PostMergeRegenerationDispatcher.dispatch`` directly with a recording workflow backend and
    an SDK client bound to the test server, so the real definition-gathering queries run against a real
    graph. The recorder makes the dispatch itself the observable, so the plain-async path needs neither
    the branch-merge flow nor the task manager. The gate decision matrix, member narrowing and the
    blanket-fallback branches are covered by the selective-regen unit tests; this proves the concrete
    ``load_definitions`` gathering and the dispatch wiring hold end to end.
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
        workflow_recorder.reset()

    @pytest.fixture(autouse=True)
    def enable_selective(self) -> Generator[None, None, None]:
        original = config.SETTINGS.main.selective_execution_after_merge
        config.SETTINGS.main.selective_execution_after_merge = True
        yield
        config.SETTINGS.main.selective_execution_after_merge = original

    def _context(self, account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=default_branch.name),
            account=AccountSession(account_id=account.id, auth_type=AuthType.API),
        )

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=SELECTIVE_SCHEMA, update_db=True)

        device1 = await Node.init(db=db, schema="TestNetworkDevice")
        await device1.new(db=db, name="dev1", color="red")
        await device1.save(db=db)
        device2 = await Node.init(db=db, schema="TestNetworkDevice")
        await device2.new(db=db, name="dev2", color="blue")
        await device2.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name="merge-selective-repo", location="https://github.com/test/merge-selective-repo.git")
        await repo.save(db=db)

        # ``models`` is populated by the GraphQL mutation analyzer in production; nodes created directly
        # against the database must set it so the data-change (MODIFIED_KINDS) gate has kinds to match.
        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="GetDevice", query=DEVICE_QUERY, models=["TestNetworkDevice"])
        await query.save(db=db)

        transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
        await transform.new(
            db=db,
            name="render-jinja",
            query=query,
            repository=repo,
            template_path="templates/device.j2",
            dependencies=[".infrahub.yml", "templates/device.j2"],
            dependencies_complete=True,
        )
        await transform.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="regen-targets", members=[device1, device2])
        await group.save(db=db)

        artdef = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef.new(
            db=db,
            name="device-artifact",
            targets=group,
            transformation=transform,
            content_type="text/plain",
            artifact_name="device-config",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef.save(db=db)

        gendef = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
        await gendef.new(
            db=db,
            name="device-generator",
            query=query,
            repository=repo,
            targets=group,
            file_path="generators/device.py",
            class_name="DeviceGenerator",
            parameters={"value": {"name": "name__value"}},
            convert_query_response=False,
            execute_in_proposed_change=False,
            execute_after_merge=True,
            dependencies=[".infrahub.yml", "generators/device.py"],
            dependencies_complete=True,
        )
        await gendef.save(db=db)

        await create_branch(branch_name=SOURCE_BRANCH, db=db)

        return {"source_branch": SOURCE_BRANCH, "device1_id": device1.id}

    async def test_relevant_kind_change_selects_matching_definitions(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        client: InfrahubClient,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A data change on a queried kind awaits the generator, then targets artifacts from its output.

        The dispatcher loads the real definitions from the graph, awaits the selected generator, and
        selects the consuming artifacts from a diff of the generator's writes (stubbed here, since the
        recorded run performs none). The affected artifact is dispatched by a selective request, never a
        blanket regeneration.
        """
        await DiffSummaryCache(
            cache=memory_cache, serializer=DiffSummarySerializer(), key_namespace="branch_merge"
        ).set(
            diff_id=DIFF_CACHE_KEY,
            diff_summary=[make_node_diff(dataset["device1_id"], "TestNetworkDevice", default_branch.name, ["name"])],
        )
        capturer = _StubGeneratorDiffCapturer(
            diff_summary=[make_node_diff(dataset["device1_id"], "TestNetworkDevice", default_branch.name, ["name"])]
        )
        dispatcher = PostMergeRegenerationDispatcher(
            workflow=workflow_recorder,
            planner=build_merge_selective_regeneration(
                client=client,
                log=logging.getLogger("test"),
                generator_output=GeneratorCascadeOutput(capturer=capturer),
            ),
            summary_cache=DiffSummaryCache(
                cache=memory_cache, serializer=DiffSummarySerializer(), key_namespace="branch_merge"
            ),
            log=logging.getLogger("test"),
        )
        await dispatcher.dispatch(
            context=self._context(admin_account, default_branch),
            target_branch=default_branch.name,
            merge_diff_cache_key=DIFF_CACHE_KEY,
        )

        generator_calls = workflow_recorder.get_execute_calls_for(REQUEST_GENERATOR_DEFINITION_RUN)
        assert [call["parameters"]["model"].generator_definition.definition_name for call in generator_calls] == [
            "device-generator"
        ]
        # No existing subscribers, so every live member is new and the filter collapses to "all".
        assert generator_calls[0]["parameters"]["model"].target_members == []
        # The generator is awaited (never submitted) and its output is captured to drive the selection.
        assert workflow_recorder.get_submit_calls_for(REQUEST_GENERATOR_DEFINITION_RUN) == []
        assert capturer.calls == 1
        # The affected artifact is regenerated by a selective request, not the blanket trigger.
        artifact_names = {
            call["parameters"]["model"].artifact_definition_name
            for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)
        }
        assert artifact_names == {"device-artifact"}
        assert workflow_recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE) == []
