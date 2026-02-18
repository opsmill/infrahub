import pytest
from infrahub_sdk.timestamp import Timestamp
from pytz import timezone

from infrahub.auth import authenticate_with_password, authentication_token, validate_active_account
from infrahub.core import registry
from infrahub.core.account import validate_token
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import AuthorizationError
from infrahub.models import PasswordCredential


async def test_validate_user_create(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)
    account_token_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNTTOKEN, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123")
    await user1.save(db=db)
    token1 = await Node.init(db=db, schema=account_token_schema)
    await token1.new(db=db, token="123456789", account=user1)
    await token1.save(db=db)


async def test_validate_token(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)
    account_token_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNTTOKEN, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123")
    await user1.save(db=db)
    user2 = await Node.init(db=db, schema=account_schema)
    await user2.new(db=db, name="user2", password="User2Password234")
    await user2.save(db=db)
    token1 = await Node.init(db=db, schema=account_token_schema)
    await token1.new(db=db, token="123456789", account=user1)
    await token1.save(db=db)

    assert await validate_token(token="123456789", db=db) == user1.id
    assert await validate_token(token="987654321", db=db) is None

    # with future expiration
    right_now = Timestamp()
    future = right_now.add(minutes=1)
    token1.expiration.value = future.to_string()
    await token1.save(db=db)
    assert await validate_token(token="123456789", db=db) == user1.id

    branch = await create_branch(db=db, branch_name="token_branch")

    # test with updated account
    token1 = await NodeManager.get_one(db=db, branch=branch, id=token1.id)
    await token1.account.update(db=db, data=user2)
    await token1.save(db=db)
    assert await validate_token(token="123456789", db=db, branch=branch) == user2.id

    # test updated token value
    token1 = await NodeManager.get_one(db=db, branch=branch, id=token1.id)
    token1.token.value = "123454321"
    await token1.save(db=db)
    assert await validate_token(token="123454321", db=db, branch=branch) == user2.id
    assert await validate_token(token="123456789", db=db, branch=branch) is None

    # test updated past expiration
    token1 = await NodeManager.get_one(db=db, branch=branch, id=token1.id)
    past = right_now.add(minutes=-1)
    token1.expiration.value = past.to_string()
    await token1.save(db=db)
    assert await validate_token(token="123454321", db=db, branch=branch) is None

    # test updated past expiration with tz
    token1 = await NodeManager.get_one(db=db, branch=branch, id=token1.id)
    past = right_now.add(minutes=-1)
    # UTC-7
    past_with_tz = past.to_datetime().astimezone(timezone("US/Pacific"))
    token1.expiration.value = past_with_tz.isoformat()
    await token1.save(db=db)
    assert await validate_token(token="123454321", db=db, branch=branch) is None

    # test updated future expiration with tz
    token1 = await NodeManager.get_one(db=db, branch=branch, id=token1.id)
    future = right_now.add(minutes=1)
    # UTC+9
    future_with_tz = future.to_datetime().astimezone(timezone("Asia/Tokyo"))
    token1.expiration.value = future_with_tz.isoformat()
    await token1.save(db=db)
    assert await validate_token(token="123454321", db=db, branch=branch) == user2.id

    # test delete works
    await token1.delete(db=db)
    assert await validate_token(token="123454321", db=db) is None


async def test_account_status(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123")
    await user1.save(db=db)
    user2 = await Node.init(db=db, schema=account_schema)
    await user2.new(db=db, name="user2", password="User1Password123", status="inactive")
    await user2.save(db=db)

    await validate_active_account(db=db, account_id=user1.id)

    with pytest.raises(AuthorizationError, match="This account has been deactivated"):
        await validate_active_account(db=db, account_id=user2.id)


async def test_authenticate_with_password(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123")
    await user1.save(db=db)
    user2 = await Node.init(db=db, schema=account_schema)
    await user2.new(db=db, name="user2", password="User1Password123", status="inactive")
    await user2.save(db=db)

    assert await authenticate_with_password(
        db=db, credentials=PasswordCredential(username=user1.name.value, password="User1Password123")
    )
    with pytest.raises(AuthorizationError, match="This account is not allowed to login"):
        await authenticate_with_password(
            db=db, credentials=PasswordCredential(username=user2.name.value, password="User1Password123")
        )


async def test_authenticate_token(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)
    account_token_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNTTOKEN, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123")
    await user1.save(db=db)
    token1 = await Node.init(db=db, schema=account_token_schema)
    await token1.new(db=db, token="123456789", account=user1)
    await token1.save(db=db)

    user2 = await Node.init(db=db, schema=account_schema)
    await user2.new(db=db, name="user2", password="User1Password123", status="inactive")
    await user2.save(db=db)
    token2 = await Node.init(db=db, schema=account_token_schema)
    await token2.new(db=db, token="abcdef", account=user2)
    await token2.save(db=db)

    assert await authentication_token(db=db, api_key=token1.token.value)
    with pytest.raises(AuthorizationError, match="This account has been deactivated"):
        await authentication_token(db=db, api_key=token2.token.value)
