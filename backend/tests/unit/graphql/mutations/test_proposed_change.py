from uuid import uuid4

from infrahub_sdk import InfrahubClient
from prefect.client.orchestration import get_client

from infrahub.auth import AccountSession, AuthType
from infrahub.core.branch import Branch
from infrahub.core.constants import CheckType, InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.message_bus import messages
from infrahub.message_bus.types import KVTTL
from infrahub.permissions.local_backend import LocalPermissionBackend
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.worker import WORKER_IDENTITY
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
  ) {
  CoreProposedChangeCreate(
    data: {
      name: {value: $name},
      source_branch: {value: $source},
      destination_branch: {value: $destination}
    }
  ) {
    ok
    object {
      id
    }
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


async def test_create_invalid_branch_combinations(db: InfrahubDatabase, default_branch, register_core_models_schema):
    branch_name = str(uuid4().hex)
    invalid_branch = str(uuid4().hex)
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
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


async def test_trigger_proposed_change(
    db: InfrahubDatabase, register_core_models_schema: None, create_test_admin: Node
) -> None:
    branch_name = "triggered-proposed-change"
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(db=db, name="change123", destination_branch="main", source_branch=branch_name)
    await proposed_change.save(db=db)
    all_recorder = BusRecorder()
    service = await InfrahubServices.new(database=db, message_bus=all_recorder)
    account_session = AccountSession(
        authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
    )
    all_result = await graphql_mutation(
        query=RUN_CHECK,
        db=db,
        variables={"proposed_change": proposed_change.id},
        service=service,
        account_session=account_session,
    )
    assert all_result.data
    assert not all_result.errors

    artifact_recorder = BusRecorder()
    service = await InfrahubServices.new(database=db, message_bus=artifact_recorder)
    artifact_result = await graphql_mutation(
        query=RUN_CHECK,
        db=db,
        variables={"proposed_change": proposed_change.id, "check_type": "ARTIFACT"},
        service=service,
        account_session=account_session,
    )

    update_status = await graphql_mutation(
        query=UPDATE_PROPOSED_CHANGE,
        db=db,
        variables={"proposed_change": proposed_change.id, "state": "canceled"},
        service=service,
        account_session=account_session,
    )

    cancelled_recorder = BusRecorder()
    service = await InfrahubServices.new(database=db, message_bus=cancelled_recorder)
    canceled_result = await graphql_mutation(
        query=RUN_CHECK,
        db=db,
        variables={"proposed_change": proposed_change.id, "check_type": "DATA"},
        service=service,
        account_session=account_session,
    )

    assert len(all_recorder.messages) == 1
    assert isinstance(all_recorder.messages[0], messages.RequestProposedChangePipeline)
    message = all_recorder.messages[0]
    assert message.check_type == CheckType.ALL

    assert artifact_result.data
    assert not artifact_result.errors
    assert len(artifact_recorder.messages) == 1
    assert isinstance(artifact_recorder.messages[0], messages.RequestProposedChangePipeline)
    message = artifact_recorder.messages[0]
    assert message.check_type == CheckType.ARTIFACT

    assert not update_status.errors
    assert canceled_result.errors
    assert "Unable to trigger check on proposed changes that aren't in the open state" in str(canceled_result.errors[0])
    assert not cancelled_recorder.messages


async def test_update_merged_proposed_change(db: InfrahubDatabase, register_core_models_schema: None):
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


class TestMergeProposedChangePermissionFailure(TestInfrahubApp):
    async def test_merge_proposed_change_permission_failure(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: None,
        session_first_account: AccountSession,
        session_admin: AccountSession,
        client: InfrahubClient,
    ):
        service = await InfrahubServices.new(
            database=db,
            message_bus=BusRecorder(),
            workflow=WorkflowLocalExecution(),
            cache=MemoryCache(),
            client=client,
        )
        async with get_client(sync_client=False) as prefect_client:
            await setup_worker_pools(client=prefect_client)
            await setup_deployments(prefect_client)

        registry.permission_backends = [LocalPermissionBackend()]

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
):
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
