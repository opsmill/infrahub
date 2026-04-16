from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config
from infrahub.auth import AccountSession, AuthType
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.services import InfrahubServices
from tests.helpers.graphql import graphql_mutation

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

DELETE_ACCOUNT = """
mutation CoreAccountDelete($id: String!) {
    CoreAccountDelete(data: { id: $id }) {
        ok
    }
}
"""


async def test_delete_account_with_initial_admin_token_is_rejected(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
) -> None:
    """Accounts associated with the initial admin token cannot be deleted."""
    admin_token_value = "test-initial-admin-token"
    original_token = config.SETTINGS.initial.admin_token
    config.SETTINGS.initial.admin_token = admin_token_value
    try:
        admin_account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await admin_account.new(db=db, name="admin", account_type="User", password="admin-password")
        await admin_account.save(db=db)

        token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
        await token.new(db=db, token=admin_token_value, name="admin-token", account=admin_account)
        await token.save(db=db)

        other_account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await other_account.new(db=db, name="other-user", account_type="User", password="other-password")
        await other_account.save(db=db)

        service = await InfrahubServices.new(database=db)
        account_session = AccountSession(authenticated=True, account_id=other_account.id, auth_type=AuthType.API)

        result = await graphql_mutation(
            query=DELETE_ACCOUNT,
            db=db,
            variables={"id": admin_account.id},
            service=service,
            account_session=account_session,
        )

        assert result.errors
    finally:
        config.SETTINGS.initial.admin_token = original_token


async def test_self_deletion_is_rejected(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
) -> None:
    """Users cannot delete their own account."""
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="self-delete-user", account_type="User", password="password123")
    await account.save(db=db)

    service = await InfrahubServices.new(database=db)
    account_session = AccountSession(authenticated=True, account_id=account.id, auth_type=AuthType.API)

    result = await graphql_mutation(
        query=DELETE_ACCOUNT,
        db=db,
        variables={"id": account.id},
        service=service,
        account_session=account_session,
    )

    assert result.errors
