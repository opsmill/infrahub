import bcrypt
import pytest
from graphql import graphql

from infrahub.auth import AccountSession, AuthType
from infrahub.core.branch import Branch
from infrahub.core.constants import AccountRole
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


@pytest.mark.parametrize("role", [e.value for e in AccountRole])
async def test_everyone_can_update_password(db: InfrahubDatabase, default_branch: Branch, first_account, role):
    new_password = "NewP@ssw0rd"
    new_description = "what a cool description"
    query = """
    mutation {
        CoreAccountSelfUpdate(data: {password: "%s", description: "%s"}) {
            ok
        }
    }
    """ % (new_password, new_description)

    gql_params = prepare_graphql_params(
        db=db,
        include_subscription=False,
        branch=default_branch,
        account_session=AccountSession(
            authenticated=True, account_id=first_account.id, role=role, auth_type=AuthType.JWT
        ),
    )

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["CoreAccountSelfUpdate"]["ok"] is True

    updated_account = await NodeManager.get_one(db=db, id=first_account.id, branch=default_branch)
    assert bcrypt.checkpw(new_password.encode("UTF-8"), updated_account.password.value.encode("UTF-8"))
    assert updated_account.description.value == new_description
