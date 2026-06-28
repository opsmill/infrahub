"""Component tests for the telemetry gather flow and payload resilience."""

from infrahub.core import registry
from infrahub.core.constants import AccountStatus, InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.telemetry.tasks import count_active_branches, gather_account_information


async def _create_account(db: InfrahubDatabase, name: str, status: str) -> None:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name=name, account_type="User", password=" accountPassword123", status=status)
    await account.save(db=db)


async def _create_account_group(db: InfrahubDatabase, name: str) -> None:
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name=name)
    await group.save(db=db)


async def test_gather_account_information_counts(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    # Two active + one inactive account, and two account groups.
    await _create_account(db=db, name="active-one", status=AccountStatus.ACTIVE.value)
    await _create_account(db=db, name="active-two", status=AccountStatus.ACTIVE.value)
    await _create_account(db=db, name="inactive-one", status=AccountStatus.INACTIVE.value)
    await _create_account_group(db=db, name="group-one")
    await _create_account_group(db=db, name="group-two")

    data = await gather_account_information.fn(db=db)

    # Only the two active accounts are counted; the inactive one is excluded.
    assert data.active == 2
    assert data.groups == 2


async def test_active_branches_excludes_default_and_global(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    # The registry already holds the default (main) and global (-global-) branches. Add two
    # open branches; only those two must be counted as active.
    await create_branch(branch_name="feature-a", db=db)
    await create_branch(branch_name="feature-b", db=db)

    # The default and global branches are present and excluded by the active count.
    assert any(branch.is_default for branch in registry.branch.values())
    assert any(branch.is_global for branch in registry.branch.values())

    assert await count_active_branches() == 2
