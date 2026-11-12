from collections.abc import Generator

import pytest

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.permissions import LocalPermissionBackend
from infrahub.permissions.cache_registry import reset_account_permission_cache
from infrahub.permissions.globals import get_or_create_global_permission

CACHE_TTL_SECONDS = 60


@pytest.fixture
def permission_cache_enabled() -> Generator[None, None, None]:
    original_ttl = config.SETTINGS.security.auth_cache_ttl_seconds
    config.SETTINGS.security.auth_cache_ttl_seconds = CACHE_TTL_SECONDS
    reset_account_permission_cache()
    yield
    config.SETTINGS.security.auth_cache_ttl_seconds = original_ttl
    reset_account_permission_cache()


async def _grant_edit_default_branch(db: InfrahubDatabase, account: Node) -> None:
    permission = await get_or_create_global_permission(db=db, permission=GlobalPermissions.EDIT_DEFAULT_BRANCH)
    role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role.new(db=db, name="editors", permissions=[permission])
    await role.save(db=db)
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="editors", roles=[role], members=[account])
    await group.save(db=db)


async def _global_actions(db: InfrahubDatabase, branch: Branch, session: AccountSession) -> set[str]:
    permissions = await LocalPermissionBackend().load_permissions(db=db, branch=branch, account_session=session)
    return {permission.action for permission in permissions["global_permissions"]}


async def test_permissions_granted_within_the_ttl_are_served_after_it_is_reset(
    db: InfrahubDatabase,
    default_branch: Branch,
    first_account: Node,
    session_first_account: AccountSession,
    permission_cache_enabled: None,
) -> None:
    assert await _global_actions(db=db, branch=default_branch, session=session_first_account) == set()

    await _grant_edit_default_branch(db=db, account=first_account)

    assert await _global_actions(db=db, branch=default_branch, session=session_first_account) == set()
    reset_account_permission_cache()
    assert await _global_actions(db=db, branch=default_branch, session=session_first_account) == {
        GlobalPermissions.EDIT_DEFAULT_BRANCH.value
    }


async def test_accounts_do_not_share_cached_permissions(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    session_first_account: AccountSession,
    permission_cache_enabled: None,
) -> None:
    assert GlobalPermissions.SUPER_ADMIN.value in await _global_actions(
        db=db, branch=default_branch, session=session_admin
    )

    assert await _global_actions(db=db, branch=default_branch, session=session_first_account) == set()
