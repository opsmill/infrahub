import bcrypt

from infrahub.auth import AccountSession, AuthType
from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def test_everyone_can_update_password(db: InfrahubDatabase, default_branch: Branch, first_account) -> None:
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


async def test_permissions(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    authentication_base,
    session_admin,
    first_account,
) -> None:
    query = """
    query {
        InfrahubPermissions {
            global_permissions {
                edges {
                    node {
                        display_label
                    }
                }
            }
            object_permissions {
                edges {
                    node {
                        display_label
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
    perms = [
        edge["node"]["display_label"] for edge in result.data["InfrahubPermissions"]["global_permissions"]["edges"]
    ]
    assert perms == [
        str(GlobalPermission(action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value))
    ]

    perms = [
        edge["node"]["display_label"] for edge in result.data["InfrahubPermissions"]["object_permissions"]["edges"]
    ]
    assert perms == [
        str(
            ObjectPermission(
                namespace="*", name="*", action=PermissionAction.ANY.value, decision=PermissionDecision.ALLOW_ALL.value
            )
        )
    ]

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
