from infrahub.core import registry
from infrahub.core.account import validate_token
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def test_validate_user_create(db: InfrahubDatabase, default_branch, register_core_models_schema):
    account_schema = registry.get_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)
    account_token_schema = registry.get_schema(name=InfrahubKind.ACCOUNTTOKEN, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123")
    await user1.save(db=db)
    token1 = await Node.init(db=db, schema=account_token_schema)
    await token1.new(db=db, token="123456789", account=user1)
    await token1.save(db=db)


async def test_validate_token(db: InfrahubDatabase, default_branch, register_core_models_schema):
    account_schema = registry.get_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)
    account_token_schema = registry.get_schema(name=InfrahubKind.ACCOUNTTOKEN, branch=default_branch)

    user1 = await Node.init(db=db, schema=account_schema)
    await user1.new(db=db, name="user1", password="User1Password123", role="read-write")
    await user1.save(db=db)
    token1 = await Node.init(db=db, schema=account_token_schema)
    await token1.new(db=db, token="123456789", account=user1)
    await token1.save(db=db)

    assert await validate_token(token="123456789", db=db) == (user1.id, "read-write")
    assert await validate_token(token="987654321", db=db) == (None, "read-only")
