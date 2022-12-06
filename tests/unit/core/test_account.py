import pytest

from infrahub.core import registry
from infrahub.core.account import validate_token
from infrahub.core.node import Node


@pytest.mark.asyncio
async def test_validate_user_create(session, default_branch, register_core_models_schema):

    account_schema = await registry.get_schema(session=session, name="Account")
    account_token_schema = await registry.get_schema(session=session, name="AccountToken")

    user1 = await Node.init(session=session, schema=account_schema)
    await user1.new(session=session, name="user1")
    await user1.save(session=session)
    token1 = await Node.init(session=session, schema=account_token_schema)
    await token1.new(session=session, token="123456789", account=user1)
    await token1.save(session=session)


@pytest.mark.asyncio
async def test_validate_token(session, default_branch, register_core_models_schema):

    account_schema = await registry.get_schema(session=session, name="Account")
    account_token_schema = await registry.get_schema(session=session, name="AccountToken")

    user1 = await Node.init(session=session, schema=account_schema)
    await user1.new(session=session, name="user1")
    await user1.save(session=session)
    token1 = await Node.init(session=session, schema=account_token_schema)
    await token1.new(session=session, token="123456789", account=user1)
    await token1.save(session=session)

    assert await validate_token(token="123456789", session=session) == "user1"
    assert await validate_token(token="987654321", session=session) is False
