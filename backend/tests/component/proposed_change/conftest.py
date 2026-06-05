from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.diff import NodeDiff, NodeDiffElement, NodeDiffSummary

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import RepositoryInternalStatus
from infrahub.core.diff.model.diff import DiffElementType
from infrahub.message_bus.types import ProposedChangeBranchDiff, ProposedChangeRepository
from infrahub.proposed_change.branch_diff import set_diff_summary_cache
from infrahub.proposed_change.models import RequestProposedChangeRefreshArtifacts
from infrahub.proposed_change.tasks import refresh_artifacts
from infrahub.server import app
from infrahub.workers.dependencies import build_client, build_workflow
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_CHECK
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.test_app import TestInfrahubAppBase

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.services import InfrahubServices
    from tests.adapters.cache import MemoryCache
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient

# Prefect emits run-logger output through this logger; propagation is disabled by default,
# so a test that wants to read the task-log diagnostics must force it on.
FLOW_RUN_LOGGER = "prefect.flow_runs"

QUERY_UNIQUE_TARGETS = """
query GetNetworkDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges {
            node {
                name { value }
                color { value }
            }
        }
    }
}
"""

QUERY_NON_UNIQUE_TARGETS = """
query GetAllNetworkDevices {
    TestNetworkDevice {
        edges {
            node {
                name { value }
                color { value }
            }
        }
    }
}
"""


def make_node_diff(
    node_id: str,
    kind: str,
    branch: str,
    field_names: list[str],
    action: str = "updated",
) -> NodeDiff:
    """Build a NodeDiff for use in diff summary cache."""
    return NodeDiff(
        branch=branch,
        action=action,
        kind=kind,
        id=node_id,
        display_label="",
        elements=[
            NodeDiffElement(
                name=field_name,
                element_type=DiffElementType.ATTRIBUTE.value,
                action="updated",
                summary=NodeDiffSummary(added=0, updated=1, removed=0),
            )
            for field_name in field_names
        ],
    )


class ArtifactRegenTestBase(TestInfrahubAppBase):
    """Shared harness for the artifact-regeneration selection-gate component tests.

    Provides the application wiring every scenario needs - a recording workflow
    backend so dispatched regeneration requests can be inspected without running
    them, an SDK client bound to the test server, and a per-test recorder reset -
    plus the machinery to drive ``refresh_artifacts`` and read back either the set of
    definitions dispatched for regeneration or the task-log diagnostics emitted while
    deciding.

    Subclasses supply their own schema and dataset inline. Each dataset must expose
    ``proposed_change_id``, ``repository_id``, ``repository_name`` and
    ``source_branch`` so the shared refresh helpers can assemble the request.
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

    def _make_context(self, account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=default_branch.name),
            account=AccountSession(account_id=account.id, auth_type=AuthType.API),
        )

    async def _refresh_artifacts(
        self,
        *,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        diff_summary: list[dict],
        files_added: list[str] | None = None,
        files_changed: list[str] | None = None,
        files_removed: list[str] | None = None,
    ) -> None:
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
        await set_diff_summary_cache(pipeline_id=pipeline_id, diff_summary=diff_summary, cache=memory_cache)

        model = RequestProposedChangeRefreshArtifacts(
            proposed_change=dataset["proposed_change_id"],
            source_branch=dataset["source_branch"],
            source_branch_sync_with_git=True,
            destination_branch=default_branch.name,
            branch_diff=branch_diff,
        )
        await refresh_artifacts(model=model, context=self._make_context(admin_account, default_branch))

    async def _selected_definitions(
        self,
        *,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        diff_summary: list[dict],
        files_added: list[str] | None = None,
        files_changed: list[str] | None = None,
        files_removed: list[str] | None = None,
    ) -> list[str]:
        await self._refresh_artifacts(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            diff_summary=diff_summary,
            files_added=files_added,
            files_changed=files_changed,
            files_removed=files_removed,
        )
        return [
            call["parameters"]["model"].artifact_definition.definition_name
            for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
        ]

    async def _run_refresh_capturing_log(
        self,
        *,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        caplog: pytest.LogCaptureFixture,
        diff_summary: list[dict],
        files_changed: list[str] | None = None,
    ) -> list[str]:
        with caplog.at_level(logging.INFO, logger=FLOW_RUN_LOGGER):
            await self._refresh_artifacts(
                dataset=dataset,
                default_branch=default_branch,
                admin_account=admin_account,
                memory_cache=memory_cache,
                diff_summary=diff_summary,
                files_changed=files_changed,
            )
        return [record.getMessage() for record in caplog.records]
