import bcrypt

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

CORE_ACCOUNT_DELETE = """
mutation CoreAccountDelete($id: String!) {
    CoreAccountDelete(data: {id: $id}) {
        ok
    }
}
"""


async def test_everyone_can_update_password(db: InfrahubDatabase, default_branch: Branch, first_account: Node) -> None:
    new_password = "NewP@ssw0rd"
    new_description = "what a cool description"
    query = """
    mutation {
        InfrahubAccountSelfUpdate(data: {password: "%s", description: "%s"}) {
            ok
        }
    }
    """ % (new_password, new_description)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=AccountSession(authenticated=True, account_id=first_account.id, auth_type=AuthType.JWT),
    )

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubAccountSelfUpdate"]["ok"] is True

    updated_account = await NodeManager.get_one(db=db, id=first_account.id, branch=default_branch)
    assert bcrypt.checkpw(new_password.encode("UTF-8"), updated_account.password.value.encode("UTF-8"))
    assert updated_account.description.value == new_description


async def _attach_external_identity(db: InfrahubDatabase, account: Node) -> Node:
    identity = await Node.init(db=db, schema=InfrahubKind.EXTERNALIDENTITY)
    await identity.new(
        db=db,
        account=account,
        sub=f"sub-for-{account.id}",
        provider_name="ldap",
        protocol="ldap",
    )
    await identity.save(db=db)
    return identity


async def test_externally_authenticated_account_cannot_update_password(
    db: InfrahubDatabase, default_branch: Branch, first_account: Node
) -> None:
    await _attach_external_identity(db=db, account=first_account)
    rejected_password = "should-be-rejected"

    query = """
    mutation UpdateSelf($password: String!) {
        InfrahubAccountSelfUpdate(data: {password: $password}) {
            ok
        }
    }
    """

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=AccountSession(authenticated=True, account_id=first_account.id, auth_type=AuthType.JWT),
    )

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"password": rejected_password},
    )

    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].message == (
        "Password cannot be changed on accounts authenticated through an external "
        "directory; manage credentials in the provider."
    )

    untouched_account = await NodeManager.get_one(db=db, id=first_account.id, branch=default_branch)
    assert not bcrypt.checkpw(
        rejected_password.encode("UTF-8"), str(untouched_account.password.value or "").encode("UTF-8")
    )


async def test_externally_authenticated_account_can_still_update_description(
    db: InfrahubDatabase, default_branch: Branch, first_account: Node
) -> None:
    await _attach_external_identity(db=db, account=first_account)

    query = """
    mutation {
        InfrahubAccountSelfUpdate(data: {description: "managed-by-external-directory"}) {
            ok
        }
    }
    """

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=AccountSession(authenticated=True, account_id=first_account.id, auth_type=AuthType.JWT),
    )

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubAccountSelfUpdate"]["ok"] is True

    updated_account = await NodeManager.get_one(db=db, id=first_account.id, branch=default_branch)
    assert updated_account.description.value == "managed-by-external-directory"


async def test_permissions(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    authentication_base: None,
    session_admin: AccountSession,
    first_account: Node,
) -> None:
    query = """
    query {
        InfrahubPermissions {
            global_permissions {
                edges {
                    node {
                        display_label
                        identifier
                    }
                }
            }
            object_permissions {
                edges {
                    node {
                        display_label
                        identifier
                    }
                }
            }
        }
    }
    """

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=session_admin)

    result = await graphql(
        schema=gql_params.schema, source=query, context_value=gql_params.context, root_value=None, variable_values={}
    )

    assert result.errors is None
    assert result.data
    perm_display_labels = [
        edge["node"]["display_label"] for edge in result.data["InfrahubPermissions"]["global_permissions"]["edges"]
    ]
    perm_identifiers = [
        edge["node"]["identifier"] for edge in result.data["InfrahubPermissions"]["global_permissions"]["edges"]
    ]
    assert (
        perm_display_labels
        == perm_identifiers
        == [
            str(
                GlobalPermission(
                    action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
                )
            )
        ]
    )

    perm_display_labels = [
        edge["node"]["display_label"] for edge in result.data["InfrahubPermissions"]["object_permissions"]["edges"]
    ]
    perm_identifiers = [
        edge["node"]["identifier"] for edge in result.data["InfrahubPermissions"]["object_permissions"]["edges"]
    ]
    assert (
        perm_display_labels
        == perm_identifiers
        == [
            str(
                ObjectPermission(
                    namespace="*",
                    name="*",
                    action=PermissionAction.ANY.value,
                    decision=PermissionDecision.ALLOW_ALL.value,
                )
            )
        ]
    )

    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=AccountSession(authenticated=True, account_id=first_account.id, auth_type=AuthType.JWT),
    )

    result = await graphql(
        schema=gql_params.schema, source=query, context_value=gql_params.context, root_value=None, variable_values={}
    )

    assert result.errors is None
    assert result.data
    assert not result.data["InfrahubPermissions"]["global_permissions"]["edges"]


async def test_admin_cannot_delete_own_account(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    authentication_base: None,
    session_admin: AccountSession,
    create_test_admin: Node,
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=session_admin,
    )

    result = await graphql(
        schema=gql_params.schema,
        source=CORE_ACCOUNT_DELETE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": create_test_admin.id},
    )

    assert result.errors
    assert str(result.errors[0].message) == "Cannot delete your own account"
