from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.permissions import LocalPermissionBackend
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


PROPOSED_CHANGE_META_DATA_QUERY = """
    query {
        CoreProposedChange {
            edges {
                node {
                    meta {
                        created_by
                        created_at
                        updated_by
                        updated_at
                    }
                    id
                    name {
                        value
                        meta {
                            updated_by
                            updated_at
                        }
                    }
                    description {
                        value
                        meta {
                            updated_by
                            updated_at
                        }
                    }
                    reviewers {
                        meta {
                            created_at
                            updated_at
                            created_by
                            updated_by
                        }
                        edges {
                            node {
                                name {
                                    meta {
                                        updated_at
                                        updated_by
                                    }
                                    value
                                }
                                description {
                                    meta {
                                        updated_at
                                        updated_by
                                    }
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
"""


async def test_proposed_change_open(
    db: InfrahubDatabase, register_core_models_schema: None, session_admin: AccountSession
) -> None:
    registry.permission_backends = [LocalPermissionBackend()]

    branch_name = "pc-1"
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db,
        name="pc-1",
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
    assert response.data["CoreProposedChangeAvailableActions"]["count"] == 9
    assert [node["node"]["available"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]] == [
        False,
        True,
        True,
        False,
        True,
        True,
        True,
        True,
        True,
    ]
    assert [
        node["node"]["unavailability_reason"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]
    ] == [
        "The proposed change is not closed",
        None,
        None,
        "The proposed change is not a draft",
        None,
        None,
        None,
        None,
        None,
    ]


async def test_proposed_change_closed(
    db: InfrahubDatabase, register_core_models_schema: None, session_admin: AccountSession
) -> None:
    registry.permission_backends = [LocalPermissionBackend()]

    branch_name = "pc-3"
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db,
        name="pc-3",
        destination_branch="main",
        source_branch=branch_name,
        state="closed",
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
    assert response.data["CoreProposedChangeAvailableActions"]["count"] == 9

    assert [node["node"]["available"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]] == [
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    assert [
        node["node"]["unavailability_reason"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]
    ] == [
        None,
        "The proposed change is not open",
        "The proposed change is not open",
        "The proposed change is not open",
        "The proposed change is not open",
        "The proposed change is not open",
        "The proposed change is not open",
        "The proposed change is not open",
        "The proposed change is not open",
    ]


async def test_proposed_change_draft(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    session_admin: AccountSession,
    session_first_account: AccountSession,
) -> None:
    registry.permission_backends = [LocalPermissionBackend()]

    branch_name = "pc-4"
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db,
        name="pc-4",
        destination_branch="main",
        source_branch=branch_name,
        state="open",
        is_draft=True,
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
    assert response.data["CoreProposedChangeAvailableActions"]["count"] == 9

    assert [node["node"]["available"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]] == [
        False,
        True,
        False,
        True,
        True,
        True,
        True,
        True,
        False,
    ]
    assert [
        node["node"]["unavailability_reason"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]
    ] == [
        "The proposed change is not closed",
        None,
        "The proposed change is a draft",
        None,
        None,
        None,
        None,
        None,
        "The proposed change is a draft",
    ]

    response = await graphql_query(
        query=PROPOSED_CHANGE_ACTIONS,
        db=db,
        service=service,
        variables={"proposed_change_id": proposed_change.id},
        account_session=session_first_account,
    )

    assert not response.errors
    assert response.data["CoreProposedChangeAvailableActions"]["count"] == 9
    assert [node["node"]["available"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]] == [
        False,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    assert [
        node["node"]["unavailability_reason"] for node in response.data["CoreProposedChangeAvailableActions"]["edges"]
    ] == [
        "The proposed change is not closed",
        None,
        "You are not the author of the proposed change",
        "You are not the author of the proposed change",
        "You do not have the permission to perform this action",
        "You do not have the permission to perform this action",
        "You do not have the permission to perform this action",
        "You do not have the permission to perform this action",
        "The proposed change is a draft",
    ]


async def test_proposed_change_query_meta_data(
    db: InfrahubDatabase, register_core_models_schema: None, session_admin: AccountSession
) -> None:
    registry.permission_backends = [LocalPermissionBackend()]

    branch_name = "test-pc"
    source_branch = Branch(name=branch_name)
    await source_branch.save(db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db,
        name="pc-1",
        destination_branch="main",
        source_branch=branch_name,
        state="open",
        created_by=await NodeManager.get_one(db=db, id=session_admin.account_id),
    )
    await proposed_change.save(db=db)

    service = await InfrahubServices.new(database=db, message_bus=BusSimulator())

    response = await graphql_query(
        query=PROPOSED_CHANGE_META_DATA_QUERY,
        db=db,
        service=service,
        account_session=session_admin,
    )

    assert not response.errors
    assert response.data

    for prc in response.data["CoreProposedChange"]["edges"]:
        assert prc["node"]["meta"]["created_by"]
        assert prc["node"]["name"]["meta"]["updated_at"]
        assert prc["node"]["description"]["meta"]["updated_at"]
