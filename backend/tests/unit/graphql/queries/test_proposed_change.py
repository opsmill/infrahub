from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.services import InfrahubServices
from tests.adapters.message_bus import BusSimulator
from tests.helpers.graphql import graphql_query

PROPOSED_CHANGE_ACTIONS = """
query actions($proposed_change_id: String!) {
  CoreProposedChangeAvailableActions(proposed_change_id: $proposed_change_id) {
    count
    edges {
      node {
        action
        available
        unavailability_reason
      }
    }
  }
}
"""


async def test_proposed_change_available_actions(
    db: InfrahubDatabase, register_core_models_schema: None, session_admin: AccountSession
):
    branch_name = "pc-1234"
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db,
        name="pc-merged-1234",
        destination_branch="main",
        source_branch=branch_name,
        state="open",
        created_by=await NodeManager.get_one(db=db, id=session_admin.account_id),
    )
    await proposed_change.save(db=db)

    service = await InfrahubServices.new(database=db, message_bus=BusSimulator())

    response = await graphql_query(
        query=PROPOSED_CHANGE_ACTIONS,
        db=db,
        service=service,
        variables={"proposed_change_id": proposed_change.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data["CoreProposedChangeAvailableActions"]["count"] == 6
    assert [node["node"]["available"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]] == [
        False,
        True,
        True,
        False,
        False,
        False,
    ]
    assert [
        node["node"]["unavailability_reason"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]
    ] == [
        "The proposed change is not closed, canceled",
        None,
        None,
        "The proposed change is not a draft",
        "You do not have the permission to perform this action",
        "You do not have the permission to perform this action",
    ]

    proposed_change.is_draft.value = True
    await proposed_change.save(db=db)

    response = await graphql_query(
        query=PROPOSED_CHANGE_ACTIONS,
        db=db,
        service=service,
        variables={"proposed_change_id": proposed_change.id},
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data["CoreProposedChangeAvailableActions"]["count"] == 6

    assert [node["node"]["available"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]] == [
        False,
        True,
        False,
        True,
        False,
        False,
    ]
    assert [
        node["node"]["unavailability_reason"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]
    ] == [
        "The proposed change is not closed, canceled",
        None,
        "The proposed change is a draft",
        None,
        "You do not have the permission to perform this action",
        "The proposed change is a draft",
    ]
