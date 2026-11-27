from collections.abc import Generator

import pytest

from infrahub import config
from infrahub.auth.auth import validate_api_key
from infrahub.auth.cache_registry import reset_account_token_cache
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import AuthorizationError

CACHE_TTL_SECONDS = 60
TOKEN = "123456789"


@pytest.fixture
def token_cache_enabled() -> Generator[None, None, None]:
    original_ttl = config.SETTINGS.security.auth_cache_ttl_seconds
    config.SETTINGS.security.auth_cache_ttl_seconds = CACHE_TTL_SECONDS
    reset_account_token_cache()
    yield
    config.SETTINGS.security.auth_cache_ttl_seconds = original_ttl
    reset_account_token_cache()


@pytest.fixture
async def account_with_token(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> tuple[Node, Node]:
    account_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNT, branch=default_branch)
    account_token_schema = registry.schema.get_node_schema(name=InfrahubKind.ACCOUNTTOKEN, branch=default_branch)
    account = await Node.init(db=db, schema=account_schema)
    await account.new(db=db, name="user1", password="User1Password123")
    await account.save(db=db)
    token = await Node.init(db=db, schema=account_token_schema)
    await token.new(db=db, token=TOKEN, account=account)
    await token.save(db=db)
    return account, token


async def test_a_token_changed_within_the_ttl_still_authenticates_until_the_cache_is_reset(
    db: InfrahubDatabase, account_with_token: tuple[Node, Node], token_cache_enabled: None
) -> None:
    account, token = account_with_token
    session = await validate_api_key(db=db, token=TOKEN)
    assert session.account_id == account.id

    token.token.value = "987654321"
    await token.save(db=db)

    session = await validate_api_key(db=db, token=TOKEN)
    assert session.account_id == account.id

    reset_account_token_cache()
    with pytest.raises(AuthorizationError, match=r"Invalid token"):
        await validate_api_key(db=db, token=TOKEN)


async def test_an_unknown_token_is_rejected_and_not_remembered(
    db: InfrahubDatabase, account_with_token: tuple[Node, Node], token_cache_enabled: None
) -> None:
    with pytest.raises(AuthorizationError, match=r"Invalid token"):
        await validate_api_key(db=db, token="unknown")

    account, token = account_with_token
    token.token.value = "unknown"
    await token.save(db=db)

    session = await validate_api_key(db=db, token="unknown")
    assert session.account_id == account.id
