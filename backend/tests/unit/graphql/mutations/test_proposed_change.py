from uuid import uuid4

from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.constants import CheckType, InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql_mutation

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

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
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


async def test_trigger_proposed_change(db: InfrahubDatabase, register_core_models_schema: None):
    branch_name = "triggered-proposed-change"
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(db=db, name="change123", destination_branch="main", source_branch=branch_name)
    await proposed_change.save(db=db)
    all_recorder = BusRecorder()
    service = InfrahubServices(database=db, message_bus=all_recorder)
    all_result = await graphql_mutation(
        query=RUN_CHECK, db=db, variables={"proposed_change": proposed_change.id}, service=service
    )

    artifact_recorder = BusRecorder()
    service = InfrahubServices(database=db, message_bus=artifact_recorder)
    artifact_result = await graphql_mutation(
        query=RUN_CHECK,
        db=db,
        variables={"proposed_change": proposed_change.id, "check_type": "ARTIFACT"},
        service=service,
    )

    update_status = await graphql_mutation(
        query=UPDATE_PROPOSED_CHANGE, db=db, variables={"proposed_change": proposed_change.id, "state": "canceled"}
    )

    cancelled_recorder = BusRecorder()
    service = InfrahubServices(database=db, message_bus=cancelled_recorder)
    canceled_result = await graphql_mutation(
        query=RUN_CHECK,
        db=db,
        variables={"proposed_change": proposed_change.id, "check_type": "DATA"},
        service=service,
    )

    assert all_result.data
    assert not all_result.errors
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

    update_status = await graphql_mutation(
        query=UPDATE_PROPOSED_CHANGE, db=db, variables={"proposed_change": proposed_change.id, "state": "canceled"}
    )

    assert update_status.errors
    assert "A proposed change in the merged state is not allowed to be updated" in str(update_status.errors[0])
