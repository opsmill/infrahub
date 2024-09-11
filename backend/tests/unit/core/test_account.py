import pytest

from infrahub.auth import authenticate_with_password, authentication_token, validate_active_account
from infrahub.core import registry
from infrahub.core.account import validate_token
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import AuthorizationError
from infrahub.models import PasswordCredential


async def test_validate_user_create(db: InfrahubDatabase, default_branch, register_core_models_schema):
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)
    account_token_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNTTOKEN, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123")
    await user1.save(db=db)
    token1 = await Node.init(db=db, schema=account_token_schema)
    await token1.new(db=db, token="123456789", account=user1)
    await token1.save(db=db)


async def test_validate_token(db: InfrahubDatabase, default_branch, register_core_models_schema):
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)
    account_token_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNTTOKEN, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123", role="read-write")
    await user1.save(db=db)
    token1 = await Node.init(db=db, schema=account_token_schema)
    await token1.new(db=db, token="123456789", account=user1)
    await token1.save(db=db)

    assert await validate_token(token="123456789", db=db) == (user1.id, "read-write")
    assert await validate_token(token="987654321", db=db) == (None, "read-only")


async def test_account_status(db: InfrahubDatabase, default_branch, register_core_models_schema):
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123", role="read-write")
    await user1.save(db=db)
    user2 = await Node.init(db=db, schema=account_schema)
    await user2.new(db=db, name="user2", password="User1Password123", role="read-write", status="inactive")
    await user2.save(db=db)

    await validate_active_account(db=db, account_id=user1.id)

    with pytest.raises(AuthorizationError, match="This account has been deactivated"):
        await validate_active_account(db=db, account_id=user2.id)


async def test_authenticate_with_password(db: InfrahubDatabase, default_branch, register_core_models_schema):
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123", role="read-write")
    await user1.save(db=db)
    user2 = await Node.init(db=db, schema=account_schema)
    await user2.new(db=db, name="user2", password="User1Password123", role="read-write", status="inactive")
    await user2.save(db=db)

    assert await authenticate_with_password(
        db=db, credentials=PasswordCredential(username=user1.name.value, password="User1Password123")
    )
    with pytest.raises(AuthorizationError, match="This account is not allowed to login"):
        await authenticate_with_password(
            db=db, credentials=PasswordCredential(username=user2.name.value, password="User1Password123")
        )


async def test_authenticate_token(db: InfrahubDatabase, default_branch, register_core_models_schema):
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)
    account_token_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNTTOKEN, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123", role="read-write")
    await user1.save(db=db)
    token1 = await Node.init(db=db, schema=account_token_schema)
    await token1.new(db=db, token="123456789", account=user1)
    await token1.save(db=db)

    user2 = await Node.init(db=db, schema=account_schema)
    await user2.new(db=db, name="user2", password="User1Password123", role="read-write", status="inactive")
    await user2.save(db=db)
    token2 = await Node.init(db=db, schema=account_token_schema)
    await token2.new(db=db, token="abcdef", account=user2)
    await token2.save(db=db)

    assert await authentication_token(db=db, api_key=token1.token.value)
    with pytest.raises(AuthorizationError, match="This account has been deactivated"):
        await authentication_token(db=db, api_key=token2.token.value)
