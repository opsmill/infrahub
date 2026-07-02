from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.uuidt import UUIDT

from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.initialization import create_account
from infrahub.webhook.tasks import webhook_process
from infrahub.workers.dependencies import build_http_service
from tests.adapters.http import MemoryHTTP
from tests.helpers.permissions import define_permissions
from tests.helpers.test_app import TestInfrahubApp

from .conftest import BRANCH_CREATED_PAYLOAD, OPERATOR_BRANCH, only_new_run, read_send_runs

if TYPE_CHECKING:
    from fast_depends import Provider
    from prefect.client.schemas.objects import FlowRun

    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.task_manager.flow_run.prefect_client import FlowRunQuerying
    from tests.helpers.test_client import InfrahubTestClient


WEBHOOK_TARGET_URL = "https://url.mock"


class TestWebhookRetry(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def api_branch_operator_token(self) -> str:
        return str(UUIDT())

    @pytest.fixture(scope="class")
    async def operator_branch(self, client: InfrahubClient, initial_dataset: None) -> None:
        await client.branch.create(branch_name=OPERATOR_BRANCH, sync_with_git=False)

    @pytest.fixture(scope="class")
    async def branch_operator_client(
        self,
        db: InfrahubDatabase,
        register_core_schema: SchemaBranch,
        test_client: InfrahubTestClient,
        api_branch_operator_token: str,
    ) -> InfrahubClient:
        """A client for an account allowed to update any object on non-default branches only.

        The account also holds the global permission to run mutations on the default branch, so a
        denial can only come from the branch-relative object permission.
        """
        account = await create_account(
            db=db,
            name="branch-operator",
            password="branch-operator-password",
            token_value=api_branch_operator_token,
        )
        await define_permissions(
            account=account,
            db=db,
            object_permissions=[
                ObjectPermission(namespace="*", name="*", action="any", decision=PermissionDecision.ALLOW_OTHER.value)
            ],
            global_permissions=[
                GlobalPermission(
                    action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            ],
        )
        config = Config(
            api_token=api_branch_operator_token,
            requester=test_client.async_request,
            sync_requester=test_client.sync_request,
        )
        return InfrahubClient(config=config)

    async def test_retry_replays_frozen_payload_as_new_delivery(
        self,
        db: InfrahubDatabase,
        flow_run_querier: FlowRunQuerying,
        webhook1: Node,
        webhook_deployment: None,
        client: InfrahubClient,
        dependency_provider: Provider,
        immediate_webhook_retries: None,
    ) -> None:
        http = MemoryHTTP()
        http.add_post_response(
            url=WEBHOOK_TARGET_URL,
            response=httpx.Response(request=httpx.Request(method="POST", url=WEBHOOK_TARGET_URL), status_code=200),
        )

        with dependency_provider.scope(build_http_service, lambda: http):
            before = {str(run.id) for run in await read_send_runs(flow_run_querier)}
            await webhook_process(
                webhook_id=webhook1.id,
                webhook_name="Webhook1",
                webhook_kind=InfrahubKind.STANDARDWEBHOOK,
                branch_name="main",
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

            original = only_new_run(await read_send_runs(flow_run_querier), before)
            original_payload = original.parameters["payload"]
            seen = before | {str(original.id)}

            # The retry submits the delivery synchronously here, so the mock must stay in scope.
            mutation = Mutation(
                mutation="InfrahubTaskRetry",
                input_data={"data": {"id": str(original.id)}},
                query={"ok": None, "task": {"id": None}},
            )
            result = await client.execute_graphql(query=mutation.render())

        assert result["InfrahubTaskRetry"]["ok"] is True
        assert result["InfrahubTaskRetry"]["task"]["id"]

        # The retry produced a new, independent delivery replaying the frozen payload.
        post_runs = await read_send_runs(flow_run_querier)
        new_run = only_new_run(post_runs, seen)
        assert new_run.parameters["payload"] == original_payload

        # The original delivery is left untouched as an immutable record.
        unchanged = next(run for run in post_runs if str(run.id) == str(original.id))
        assert unchanged.parameters["payload"] == original_payload

    async def test_retry_in_progress_delivery_is_rejected(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        client: InfrahubClient,
        scheduled_send_run: FlowRun,
    ) -> None:
        mutation = Mutation(
            mutation="InfrahubTaskRetry",
            input_data={"data": {"id": str(scheduled_send_run.id)}},
            query={"ok": None, "task": {"id": None}},
        )
        with pytest.raises(Exception, match=r"Retry is unavailable: Delivery still in progress\."):
            await client.execute_graphql(query=mutation.render())

    async def test_retry_denied_without_permission(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        unprivileged_client: InfrahubClient,
        settled_send_run: FlowRun,
    ) -> None:
        mutation = Mutation(
            mutation="InfrahubTaskRetry",
            input_data={"data": {"id": str(settled_send_run.id)}},
            query={"ok": None, "task": {"id": None}},
        )
        with pytest.raises(Exception, match="You do not have the following permission"):
            await unprivileged_client.execute_graphql(query=mutation.render())

    async def test_retry_of_default_branch_delivery_requires_default_branch_permission(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        operator_branch: None,
        branch_operator_client: InfrahubClient,
        settled_send_run: FlowRun,
    ) -> None:
        """The permission follows the delivery's branch, whichever branch the request is made on."""
        mutation = Mutation(
            mutation="InfrahubTaskRetry",
            input_data={"data": {"id": str(settled_send_run.id)}},
            query={"ok": None, "task": {"id": None}},
        )
        with pytest.raises(
            Exception,
            match=r"You do not have the following permission: object:Core:StandardWebhook:update:allow_default",
        ):
            await branch_operator_client.execute_graphql(query=mutation.render(), branch_name=OPERATOR_BRANCH)

    async def test_retry_of_branch_delivery_allowed_with_branch_scoped_permission(
        self,
        db: InfrahubDatabase,
        flow_run_querier: FlowRunQuerying,
        webhook1: Node,
        webhook_deployment: None,
        operator_branch: None,
        branch_operator_client: InfrahubClient,
        settled_branch_send_run: FlowRun,
        dependency_provider: Provider,
    ) -> None:
        """A branch-scoped update permission allows retrying a delivery initiated from such a branch."""
        http = MemoryHTTP()
        http.add_post_response(
            url=WEBHOOK_TARGET_URL,
            response=httpx.Response(request=httpx.Request(method="POST", url=WEBHOOK_TARGET_URL), status_code=200),
        )
        before = {str(run.id) for run in await read_send_runs(flow_run_querier)}

        mutation = Mutation(
            mutation="InfrahubTaskRetry",
            input_data={"data": {"id": str(settled_branch_send_run.id)}},
            query={"ok": None, "task": {"id": None}},
        )
        with dependency_provider.scope(build_http_service, lambda: http):
            result = await branch_operator_client.execute_graphql(query=mutation.render())

        assert result["InfrahubTaskRetry"]["ok"] is True

        new_run = only_new_run(await read_send_runs(flow_run_querier), before)
        assert new_run.parameters["branch_name"] == OPERATOR_BRANCH

    async def test_retry_unknown_delivery_reports_no_longer_available(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        client: InfrahubClient,
    ) -> None:
        mutation = Mutation(
            mutation="InfrahubTaskRetry",
            input_data={"data": {"id": str(uuid4())}},
            query={"ok": None, "task": {"id": None}},
        )
        with pytest.raises(Exception, match="no longer available"):
            await client.execute_graphql(query=mutation.render())
