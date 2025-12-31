from unittest.mock import ANY, call, patch
from uuid import uuid4

from infrahub_sdk import InfrahubClient
from prefect.client.orchestration import get_client

from infrahub.auth import AccountSession, AuthType
from infrahub.components import ComponentType
from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import CheckType, GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.message_bus.types import KVTTL
from infrahub.permissions import AssignedPermissions, PermissionBackend
from infrahub.proposed_change.models import RequestProposedChangePipeline
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.services.component import InfrahubComponent
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import build_client
from infrahub.workflows.catalogue import REQUEST_PROPOSED_CHANGE_PIPELINE
from infrahub.workflows.initialization import setup_deployments, setup_worker_pools
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder, BusSimulator
from tests.helpers.graphql import graphql, graphql_mutation
from tests.helpers.test_app import TestInfrahubApp

CREATE_PROPOSED_CHANGE = """
mutation ProposedChange(
  $destination: String!,
  $name: String!,
  $source: String!
  $state: String
  ) {
  CoreProposedChangeCreate(
    data: {
      name: {value: $name},
      source_branch: {value: $source},
      destination_branch: {value: $destination}
      state: {value: $state}
    }
  ) {
    ok
    object {
      id
    }
  }
}
"""

PROPOSED_CHANGE_REVIEW = """
mutation CoreProposedChangeReview(
    $proposed_change_id: String!,
    $decision: ProposedChangeApprovalDecision!
  ) {
  CoreProposedChangeReview(data:
    {
      id: $proposed_change_id,
      decision: $decision
    }
  ) {
    ok
  }
}
"""

RUN_CHECK = """
mutation RunCheck(
    $proposed_change: String!,
    $check_type: CheckType
  ) {
  CoreProposedChangeRunCheck(data:
    {
      id: $proposed_change,
      check_type: $check_type
    }
  ) {
    ok
  }
}
"""

UPDATE_PROPOSED_CHANGE = """
mutation UpdateProposedChange(
    $proposed_change: String!,
    $state: String
  ) {
  CoreProposedChangeUpdate(data:
    {
      id: $proposed_change,
      state: {value: $state}
    }
  ) {
    ok
  }
}
"""
UPDATE_PROPOSED_CHANGE_WITH_DRAFT = """
mutation UpdateProposedChange(
    $proposed_change: String!,
    $state: String
    $draft: Boolean
  ) {
  CoreProposedChangeUpdate(data:
    {
      id: $proposed_change,
      state: {value: $state},
      is_draft: {value: $draft}
    }
  ) {
    ok
  }
}
"""


async def test_create_invalid_branch_combinations(
    db: InfrahubDatabase, default_branch, register_core_models_schema
) -> None:
    branch_name = str(uuid4().hex)
    invalid_branch = str(uuid4().hex)
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="user", password="password")
    await account.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=AccountSession(authenticated=False, account_id=account.get_id(), auth_type=AuthType.NONE),
    )
    no_source = await graphql(
        schema=gql_params.schema,
        source=CREATE_PROPOSED_CHANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"source": invalid_branch, "destination": "main", "name": "invalid-source"},
    )

    invalid_combination = await graphql(
        schema=gql_params.schema,
        source=CREATE_PROPOSED_CHANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "source": source_branch.name,
            "destination": source_branch.name,
            "name": "invalid-combination",
        },
    )

    invalid_destination = await graphql(
        schema=gql_params.schema,
        source=CREATE_PROPOSED_CHANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "source": source_branch.name,
            "destination": "not-main",
            "name": "invalid-destination",
        },
    )

    assert no_source.errors
    assert "The specified source branch for this proposed change was not found" in str(no_source.errors)

    assert invalid_combination.errors
    assert "The source and destination branch can't be the same" in str(invalid_combination.errors)

    assert invalid_destination.errors
    assert "Currently only the 'main' branch is supported as a destination for a proposed change" in str(
        invalid_destination.errors
    )


async def test_create_invalid_state_combinations(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """Validate that we can't create a PC in an invalid state.

    While this wouldn't actually do anything it looks weird from an auditing point of view to have a
    proposed change that looks like it has been merged even though it never was.
    """
    branch_name = str(uuid4().hex)
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="user", password="password")
    await account.save(db=db)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=AccountSession(authenticated=False, account_id=account.get_id(), auth_type=AuthType.NONE),
    )
    closed = await graphql(
        schema=gql_params.schema,
        source=CREATE_PROPOSED_CHANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "source": source_branch.name,
            "destination": "main",
            "name": "invalid-state",
            "state": "closed",
        },
    )
    assert closed.errors
    assert "A proposed change has to be in the open state during creation" in str(closed.errors)

    merged = await graphql(
        schema=gql_params.schema,
        source=CREATE_PROPOSED_CHANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "source": source_branch.name,
            "destination": "main",
            "name": "invalid-state",
            "state": "merged",
        },
    )

    assert closed.errors
    assert "A proposed change has to be in the open state during creation" in str(closed.errors)
    assert merged.errors
    assert "A proposed change has to be in the open state during creation" in str(merged.errors)


class DummyReviewProposedChangeAllow(PermissionBackend):
    async def load_permissions(
        self, db: InfrahubDatabase, branch: Branch, account_session: AccountSession
    ) -> AssignedPermissions:
        return {
            "global_permissions": [
                GlobalPermission(
                    action=GlobalPermissions.REVIEW_PROPOSED_CHANGE.value,
                    decision=PermissionDecision.ALLOW_ALL.value,
                )
            ],
            "object_permissions": [],
        }


async def test_cannot_approve_own_created_proposed_change(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    registry.permission_backends = [DummyReviewProposedChangeAllow()]

    branch_name = str(uuid4().hex)
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="user", password="password")
    await account.save(db=db)

    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=AccountSession(authenticated=False, account_id=account.get_id(), auth_type=AuthType.NONE),
    )
    open_proposed_change = await graphql(
        schema=gql_params.schema,
        source=CREATE_PROPOSED_CHANGE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "source": source_branch.name,
            "destination": "main",
            "name": "sample proposed change",
            "state": "open",
        },
    )
    assert not open_proposed_change.errors
    proposed_change_id = open_proposed_change.data["CoreProposedChangeCreate"]["object"]["id"]

    approve_proposed_change = await graphql(
        schema=gql_params.schema,
        source=PROPOSED_CHANGE_REVIEW,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "proposed_change_id": proposed_change_id,
            "decision": "APPROVE",
        },
    )
    assert approve_proposed_change.errors
    assert "You cannot review your own proposed changes" in str(approve_proposed_change.errors)


class TestTriggerProposedChange(TestInfrahubApp):
    async def test_trigger_proposed_change(
        self,
        db: InfrahubDatabase,
        create_test_admin: Node,
        client: InfrahubClient,
        service: InfrahubServices,
    ) -> None:
        source_branch = await create_branch(db=db, branch_name="triggered-proposed-change")

        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(db=db, name="change123", destination_branch="main", source_branch=source_branch.name)
        await proposed_change.save(db=db)
        account_session = AccountSession(
            authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
        )

        with patch(
            "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
        ) as mock_submit_workflow:
            all_result = await graphql_mutation(
                query=RUN_CHECK,
                db=db,
                variables={"proposed_change": proposed_change.id},
                service=service,
                account_session=account_session,
            )
            assert all_result.data
            assert not all_result.errors

            artifact_result = await graphql_mutation(
                query=RUN_CHECK,
                db=db,
                variables={"proposed_change": proposed_change.id, "check_type": "ARTIFACT"},
                service=service,
                account_session=account_session,
            )

            assert artifact_result.data
            assert not artifact_result.errors

            update_status = await graphql_mutation(
                query=UPDATE_PROPOSED_CHANGE,
                db=db,
                variables={"proposed_change": proposed_change.id, "state": "canceled"},
                service=service,
                account_session=account_session,
            )

            calls = mock_submit_workflow.call_args_list
            assert len(calls) == 2
            first_model = calls[0].kwargs["parameters"]["model"]
            second_model = calls[1].kwargs["parameters"]["model"]

            expected_calls = [
                call(
                    workflow=REQUEST_PROPOSED_CHANGE_PIPELINE,
                    parameters={
                        "model": RequestProposedChangePipeline(
                            pipeline_id=first_model.pipeline_id,
                            proposed_change=proposed_change.id,
                            source_branch=source_branch.name,
                            source_branch_sync_with_git=source_branch.sync_with_git,
                            destination_branch=proposed_change.destination_branch.value,
                            check_type=CheckType.ALL,
                        )
                    },
                    context=ANY,
                ),
                call(
                    workflow=REQUEST_PROPOSED_CHANGE_PIPELINE,
                    parameters={
                        "model": RequestProposedChangePipeline(
                            pipeline_id=second_model.pipeline_id,
                            proposed_change=proposed_change.id,
                            source_branch=source_branch.name,
                            source_branch_sync_with_git=source_branch.sync_with_git,
                            destination_branch=proposed_change.destination_branch.value,
                            check_type=CheckType.ARTIFACT,
                        )
                    },
                    context=ANY,
                ),
            ]
            mock_submit_workflow.assert_has_calls(expected_calls)

        with patch(
            "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
        ) as mock_submit_workflow:
            canceled_result = await graphql_mutation(
                query=RUN_CHECK,
                db=db,
                variables={"proposed_change": proposed_change.id, "check_type": "DATA"},
                service=service,
                account_session=account_session,
            )

            assert not update_status.errors
            assert canceled_result.errors
            assert "Unable to trigger check on proposed changes that aren't in the open state" in str(
                canceled_result.errors[0]
            )

            mock_submit_workflow.assert_not_called()


async def test_update_merged_proposed_change(db: InfrahubDatabase, register_core_models_schema: None) -> None:
    branch_name = "merged-proposed-change"
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db, name="pc-merged-1234", destination_branch="main", source_branch=branch_name, state="merged"
    )
    await proposed_change.save(db=db)

    service = await InfrahubServices.new(database=db, message_bus=BusSimulator())

    update_status = await graphql_mutation(
        query=UPDATE_PROPOSED_CHANGE,
        db=db,
        variables={"proposed_change": proposed_change.id, "state": "canceled"},
        service=service,
    )

    assert update_status.errors
    assert "A proposed change in the merged state is not allowed to be updated" in str(update_status.errors[0])


async def test_merge_draft_proposed_change(db: InfrahubDatabase, register_core_models_schema: None) -> None:
    branch_name = "draft-proposed-change"
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db, name="draft-pc-1234", destination_branch="main", source_branch=branch_name, state="open", is_draft=True
    )
    await proposed_change.save(db=db)

    service = await InfrahubServices.new(database=db, message_bus=BusSimulator())

    update_status = await graphql_mutation(
        query=UPDATE_PROPOSED_CHANGE,
        db=db,
        variables={"proposed_change": proposed_change.id, "state": "merged"},
        service=service,
    )

    assert update_status.errors
    assert "A draft proposed change is not allowed to be merged" in str(update_status.errors[0])

    proposed_change.is_draft.value = False
    await proposed_change.save(db=db)

    update_status = await graphql_mutation(
        query=UPDATE_PROPOSED_CHANGE_WITH_DRAFT,
        db=db,
        variables={"proposed_change": proposed_change.id, "state": "merged", "draft": True},
        service=service,
    )

    assert update_status.errors
    assert "A draft proposed change is not allowed to be merged" in str(update_status.errors[0])


async def test_merge_proposed_change_with_branch_upgrade_rebase_status(
    db: InfrahubDatabase, register_core_models_schema: None
):
    branch_name = "upgrade-rebase-status-proposed-change"
    source_branch = Branch(name=branch_name)
    source_branch.status = BranchStatus.NEED_UPGRADE_REBASE
    await source_branch.save(db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(db=db, name="pc-1234", destination_branch="main", source_branch=branch_name, state="open")
    await proposed_change.save(db=db)

    service = await InfrahubServices.new(database=db, message_bus=BusSimulator())

    update_status = await graphql_mutation(
        query=UPDATE_PROPOSED_CHANGE,
        db=db,
        variables={"proposed_change": proposed_change.id, "state": "merged"},
        service=service,
    )

    assert update_status.errors
    assert "The branch must be upgraded and rebased prior to merging the proposed change" in str(
        update_status.errors[0]
    )


class TestMergeProposedChangePermissionFailure(TestInfrahubApp):
    async def test_merge_proposed_change_permission_failure(
        self,
        db: InfrahubDatabase,
        default_permission_backend: None,
        register_core_models_schema: None,
        session_first_account: AccountSession,
        session_admin: AccountSession,
        client: InfrahubClient,
        dependency_provider,
    ) -> None:
        with dependency_provider.scope(build_client, lambda: client):
            cache = MemoryCache()
            message_bus = BusRecorder()
            service = await InfrahubServices.new(
                database=db,
                message_bus=message_bus,
                workflow=WorkflowLocalExecution(),
                cache=cache,
                client=client,
                component=InfrahubComponent(
                    cache=cache, db=db, message_bus=message_bus, component_type=ComponentType.NONE
                ),
            )

            async with get_client(sync_client=False) as prefect_client:
                await setup_worker_pools(client=prefect_client)
                await setup_deployments(prefect_client)

            branch_name = "merge-proposed-change-perm"
            branch = await create_branch(branch_name=branch_name, db=db)
            await service.cache.set(
                key=f"workers:schema_hash:branch:{str(branch.get_uuid)}:{service.component_type.value}:worker:{WORKER_IDENTITY}",
                value=branch.active_schema_hash.main,
                expires=KVTTL.TWO_HOURS,
            )
            await service.cache.set(
                key=f"workers:active:{service.component_type.value}:worker:{WORKER_IDENTITY}",
                value=Timestamp().to_string(),
                expires=KVTTL.FIFTEEN,
            )
            await service.component.refresh_heartbeat()

            proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
            await proposed_change.new(
                db=db, name="pc-merge-perm-1234", destination_branch="main", source_branch=branch_name, state="open"
            )
            await proposed_change.save(db=db)

            update_status = await graphql_mutation(
                query=UPDATE_PROPOSED_CHANGE,
                db=db,
                variables={"proposed_change": proposed_change.id, "state": "merged"},
                account_session=session_first_account,
                service=service,
            )

            assert update_status.errors
            assert update_status.errors[0].message == "You are not allowed to merge proposed changes"

            update_status = await graphql_mutation(
                query=UPDATE_PROPOSED_CHANGE,
                db=db,
                variables={"proposed_change": proposed_change.id, "state": "merged"},
                account_session=session_admin,
                service=service,
            )

            assert not update_status.errors


async def test_create_thread(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    session_first_account: AccountSession,
    session_admin: AccountSession,
) -> None:
    service = await InfrahubServices.new(
        database=db, message_bus=BusRecorder(), workflow=WorkflowLocalExecution(), cache=MemoryCache()
    )
    branch_name = "branch-1234"
    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(db=db, name="pc-1234", destination_branch="main", source_branch=branch_name, state="open")
    await proposed_change.save(db=db)

    CREATE_THREAD = """
    mutation CoreChangeThreadCreate($proposed_change: String!) {
        CoreChangeThreadCreate(
            data: {
                change: { id: $proposed_change }
                label: { value: "Conversation" }
                created_at: { value: "2025-03-05T18:01:52+01:00" }
                resolved: { value: false }
            }
        ) {
            object {
                id
                display_label
                __typename
            }
            ok
            __typename
        }
    }
    """
    response = await graphql_mutation(
        query=CREATE_THREAD,
        db=db,
        variables={"proposed_change": proposed_change.id},
        account_session=session_first_account,
        service=service,
    )
    assert not response.errors
    assert response.data
