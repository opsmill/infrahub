from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.generators.models import (
    ProposedChangeGeneratorDefinition,
    RequestGeneratorDefinitionRun,
    RequestGeneratorRun,
)
from infrahub.generators.tasks import request_generator_definition_run
from infrahub.server import app
from infrahub.workers.dependencies import build_client
from infrahub.workflows.catalogue import REQUEST_GENERATOR_RUN
from tests.adapters.workflow import WorkflowRecorder
from tests.constants.kind import TAG as TAG_KIND
from tests.helpers.dependency_override import override_dependency
from tests.helpers.schema import load_schema
from tests.helpers.schema.tag import TAG
from tests.helpers.test_app import TestInfrahubAppBase
from tests.helpers.workflow_override import override_workflow

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from fast_depends import Provider

    from infrahub.context import EventContext
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition
    from tests.helpers.test_client import InfrahubTestClient

TAG_QUERY = f"""
query GetGenTag($ids: [ID!]!) {{
    {TAG_KIND}(ids: $ids) {{
        edges {{ node {{ name {{ value }} }} }}
    }}
}}
"""

TAG_SCHEMA = SchemaRoot(nodes=[TAG])

_HEALTHY_MEMBER = "member-alpha"
_FAILING_MEMBER = "member-beta"

_DEFINITION_ID = "definition_id"
_REPOSITORY_ID = "repository_id"
_GROUP_ID = "group_id"
_QUERY_ID = "query_id"
_HEALTHY_ID = "healthy_id"
_FAILING_ID = "failing_id"


def _member_failure_message(target_name: str) -> str:
    return f"generator run failed for {target_name}"


class WorkflowRecorderFailingMember(WorkflowRecorder):
    """Records every workflow call and raises for the generator runs whose target is selected to fail or cancel.

    Simulates individual target-group members' generator runs raising while the others succeed, without
    running the real generator body. A selected member either raises an ordinary error or is cancelled.
    """

    def __init__(self) -> None:
        super().__init__()
        self.failing_target_ids: set[str] = set()
        self.cancelled_target_ids: set[str] = set()

    def reset(self) -> None:
        super().reset()
        self.failing_target_ids = set()
        self.cancelled_target_ids = set()

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type | None = None,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> Any:
        result = await super().execute_workflow(
            workflow=workflow,
            expected_return=expected_return,
            context=context,
            parameters=parameters,
            tags=tags,
            priority=priority,
        )
        if workflow == REQUEST_GENERATOR_RUN:
            model = (parameters or {})["model"]
            if isinstance(model, RequestGeneratorRun):
                if model.target_id in self.cancelled_target_ids:
                    # asyncio.gather discards this instance's message, so none is set here.
                    raise asyncio.CancelledError
                if model.target_id in self.failing_target_ids:
                    raise RuntimeError(_member_failure_message(model.target_name))
        return result


class TestGeneratorDefinitionRunReportsFailingMember(TestInfrahubAppBase):
    """One member failing must be reported per-member, not collapsed into an opaque failure.

    When a target-group member's generator run raises, the definition run's result must identify which
    member failed, so a single misbehaving target is distinguishable from every target failing.
    """

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self,
        prefect: Generator[str, None, None],
        dependency_provider: Provider,
    ) -> AsyncGenerator[WorkflowRecorderFailingMember, None]:
        recorder = WorkflowRecorderFailingMember()
        with override_workflow(recorder, dependency_provider=dependency_provider):
            yield recorder

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, test_client: InfrahubTestClient) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(scope="class")
    async def client(
        self,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        service: InfrahubServices,
        dependency_provider: Provider,
    ) -> AsyncGenerator[InfrahubClient, None]:
        sdk_client = InfrahubClient(
            config=Config(
                api_token=api_admin_token,
                requester=test_client.async_request,
                sync_requester=test_client.sync_request,
                schema_converge_timeout=5,
            )
        )
        original_client = service._client
        service._client = sdk_client
        try:
            with override_dependency(build_client, lambda: sdk_client, dependency_provider=dependency_provider):
                yield sdk_client
        finally:
            service._client = original_client

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorderFailingMember) -> None:
        workflow_recorder.reset()

    def _context(self, account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=default_branch.name),
            account=AccountSession(account_id=account.id, auth_type=AuthType.API),
        )

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> dict[str, Any]:
        await load_schema(db=db, schema=TAG_SCHEMA, update_db=True)

        healthy = await Node.init(db=db, schema=TAG_KIND)
        await healthy.new(db=db, name=_HEALTHY_MEMBER)
        await healthy.save(db=db)
        failing = await Node.init(db=db, schema=TAG_KIND)
        await failing.new(db=db, name=_FAILING_MEMBER)
        await failing.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(
            db=db,
            name="gen-member-repo",
            location="https://github.com/test/gen-member.git",
            commit="1234567890abcdef1234567890abcdef12345678",
        )
        await repo.save(db=db)

        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="GetGenTag", query=TAG_QUERY, models=[TAG_KIND])
        await query.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="member-targets", members=[healthy, failing])
        await group.save(db=db)

        gendef = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
        await gendef.new(
            db=db,
            name="tag-generator",
            query=query,
            repository=repo,
            targets=group,
            file_path="generators/tag.py",
            class_name="TagGenerator",
            parameters={"value": {"name": "name__value"}},
        )
        await gendef.save(db=db)

        return {
            _DEFINITION_ID: gendef.id,
            _REPOSITORY_ID: repo.id,
            _GROUP_ID: group.id,
            _QUERY_ID: query.id,
            _HEALTHY_ID: healthy.id,
            _FAILING_ID: failing.id,
        }

    def _model(self, dataset: dict[str, Any], branch: str) -> RequestGeneratorDefinitionRun:
        return RequestGeneratorDefinitionRun(
            branch=branch,
            generator_definition=ProposedChangeGeneratorDefinition(
                definition_id=dataset[_DEFINITION_ID],
                definition_name="tag-generator",
                class_name="TagGenerator",
                file_path="generators/tag.py",
                query_name="GetGenTag",
                query_id=dataset[_QUERY_ID],
                query_models=[TAG_KIND],
                query_payload=TAG_QUERY,
                repository_id=dataset[_REPOSITORY_ID],
                parameters={"name": "name__value"},
                group_id=dataset[_GROUP_ID],
                convert_query_response=False,
                execute_in_proposed_change=False,
                execute_after_merge=True,
            ),
        )

    async def test_failing_member_is_named_in_the_run_result(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
        workflow_recorder: WorkflowRecorderFailingMember,
    ) -> None:
        workflow_recorder.failing_target_ids = {dataset[_FAILING_ID]}

        state = await request_generator_definition_run(
            model=self._model(dataset, default_branch.name),
            context=self._context(admin_account, default_branch),
            return_state=True,
        )

        # Both members are dispatched, so the failure is one target's, not the definition's.
        dispatched = {
            call["parameters"]["model"].target_id
            for call in workflow_recorder.get_execute_calls_for(REQUEST_GENERATOR_RUN)
        }
        assert dispatched == {dataset[_HEALTHY_ID], dataset[_FAILING_ID]}

        # The result names the one failed member and its error, reporting the healthy member as
        # succeeded, rather than collapsing into an opaque failure.
        assert state.is_failed()
        assert state.message == (
            "1 of 2 generators failed, 1 succeeded: "
            f"member-beta ({dataset[_FAILING_ID]}): generator run failed for member-beta"
        )

    async def test_a_cancelled_member_propagates_the_cancellation(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
        workflow_recorder: WorkflowRecorderFailingMember,
    ) -> None:
        workflow_recorder.cancelled_target_ids = {dataset[_FAILING_ID]}

        # The cancellation propagates out of the definition run rather than being dropped by the
        # failure filter and letting the run report success.
        with pytest.raises(asyncio.CancelledError):
            await request_generator_definition_run(
                model=self._model(dataset, default_branch.name),
                context=self._context(admin_account, default_branch),
                return_state=True,
            )

        # Both members are dispatched, so the cancellation is one target's.
        dispatched = {
            call["parameters"]["model"].target_id
            for call in workflow_recorder.get_execute_calls_for(REQUEST_GENERATOR_RUN)
        }
        assert dispatched == {dataset[_HEALTHY_ID], dataset[_FAILING_ID]}
