from infrahub.auth.session import AccountSession
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus, RepositorySyncStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreGenericRepository
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
                node_metadata {
                    created_at
                    updated_at
                }
                node {

                    id
                    name {
                        value
                        updated_by {
                            id
                        }
                        updated_at
                    }
                    description {
                        value
                        updated_by {
                            id
                        }
                        updated_at
                    }
                    reviewers {
                        edges {
                            node_metadata {
                                created_at
                                updated_at
                            }
                            node {
                                name {
                                    value
                                    updated_by {
                                        id
                                    }
                                    updated_at
                                }
                                description {
                                    value
                                    updated_by {
                                        id
                                    }
                                    updated_at
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
    await create_branch(branch_name=branch_name, db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db,
        name="pc-1",
        destination_branch="main",
        source_branch=branch_name,
        state="open",
    )
    await proposed_change.save(db=db, user_id=session_admin.account_id)

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
    await create_branch(branch_name=branch_name, db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db,
        name="pc-3",
        destination_branch="main",
        source_branch=branch_name,
        state="closed",
    )
    await proposed_change.save(db=db, user_id=session_admin.account_id)

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
    await create_branch(branch_name=branch_name, db=db)

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db,
        name="pc-4",
        destination_branch="main",
        source_branch=branch_name,
        state="open",
        is_draft=True,
    )
    await proposed_change.save(db=db, user_id=session_admin.account_id)

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


async def _create_repository(db: InfrahubDatabase, kind: str, name: str) -> Node:
    repository = await Node.init(db=db, schema=kind)
    location = f"https://git.example.com/{name}.git"
    internal_status = RepositoryInternalStatus.ACTIVE.value
    if kind == InfrahubKind.READONLYREPOSITORY:
        await repository.new(db=db, name=name, location=location, ref="main", internal_status=internal_status)
    else:
        await repository.new(db=db, name=name, location=location, internal_status=internal_status)
    await repository.save(db=db)
    return repository


async def _update_repository_on_branch(
    db: InfrahubDatabase,
    repository: Node,
    branch: Branch,
    sync_status: RepositorySyncStatus,
    internal_status: RepositoryInternalStatus = RepositoryInternalStatus.ACTIVE,
) -> None:
    repository_on_branch = await NodeManager.get_one(
        db=db, id=repository.id, kind=CoreGenericRepository, branch=branch, raise_on_error=True
    )
    repository_on_branch.sync_status.value = sync_status.value
    repository_on_branch.internal_status.value = internal_status.value
    await repository_on_branch.save(db=db)


async def test_proposed_change_merge_blocked_by_repository_import(
    db: InfrahubDatabase, register_core_models_schema: None, session_admin: AccountSession
) -> None:
    registry.permission_backends = [LocalPermissionBackend()]

    failed = await _create_repository(db=db, kind=InfrahubKind.REPOSITORY, name="import-failed")
    syncing = await _create_repository(db=db, kind=InfrahubKind.READONLYREPOSITORY, name="import-syncing")
    inactive = await _create_repository(db=db, kind=InfrahubKind.REPOSITORY, name="import-inactive")
    inherited = await _create_repository(db=db, kind=InfrahubKind.REPOSITORY, name="import-inherited")
    await _update_repository_on_branch(
        db=db,
        repository=inherited,
        branch=await registry.get_branch(db=db, branch="main"),
        sync_status=RepositorySyncStatus.ERROR_IMPORT,
    )

    branch_name = "pc-import-status"
    source_branch = await create_branch(branch_name=branch_name, db=db)
    await _update_repository_on_branch(
        db=db, repository=failed, branch=source_branch, sync_status=RepositorySyncStatus.ERROR_IMPORT
    )
    await _update_repository_on_branch(
        db=db, repository=syncing, branch=source_branch, sync_status=RepositorySyncStatus.SYNCING
    )
    await _update_repository_on_branch(
        db=db,
        repository=inactive,
        branch=source_branch,
        sync_status=RepositorySyncStatus.ERROR_IMPORT,
        internal_status=RepositoryInternalStatus.INACTIVE,
    )

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db,
        name=branch_name,
        destination_branch="main",
        source_branch=branch_name,
        state="open",
    )
    await proposed_change.save(db=db, user_id=session_admin.account_id)

    service = await InfrahubServices.new(database=db, message_bus=BusSimulator())

    response = await graphql_query(
        query=PROPOSED_CHANGE_ACTIONS,
        db=db,
        service=service,
        variables={"proposed_change_id": proposed_change.id},
        account_session=session_admin,
    )

    assert not response.errors
    actions = {
        edge["node"]["action"]: (edge["node"]["available"], edge["node"]["unavailability_reason"])
        for edge in response.data["CoreProposedChangeAvailableActions"]["edges"]
    }
    assert actions["merge"] == (
        False,
        "Cannot merge. The last import of repository 'import-failed' failed: push a fix, reimport the current "
        "commit, or set the repository to inactive. Repository 'import-syncing' has not finished importing: wait "
        "for the import, or reimport the current commit if it does not finish.",
    )


async def test_proposed_change_query_meta_data(
    db: InfrahubDatabase, register_core_models_schema: None, session_admin: AccountSession
) -> None:
    registry.permission_backends = [LocalPermissionBackend()]

    branch_name = "test-pc"
    await create_branch(branch_name=branch_name, db=db)

    initial_user = "bob"
    update_user = "alice"

    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(
        db=db,
        name="pc-1",
        description="sample description",
        destination_branch="main",
        source_branch=branch_name,
        state="open",
    )
    await proposed_change.save(db=db, user_id=initial_user)
    proposed_change.description.value = "updated description"
    await proposed_change.save(db=db, user_id=update_user)

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
        assert prc["node"]["name"]["value"]
        assert prc["node"]["name"]["updated_by"]["id"] == initial_user
        assert prc["node"]["name"]["updated_at"]

        assert prc["node"]["description"]["value"]
        assert prc["node"]["description"]["updated_by"]["id"] == update_user
        assert prc["node"]["description"]["updated_at"]

        assert prc["node_metadata"]["created_at"]
        assert prc["node_metadata"]["updated_at"]
