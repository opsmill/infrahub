from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.preferences import GlobalPreference, UserPreference

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_global_preference_get_global_lazy_create(db: InfrahubDatabase, default_branch: Branch) -> None:
    # No GlobalPreference exists yet.
    assert await GlobalPreference.get_list(db=db) == []

    first = await GlobalPreference.get_global(db=db)
    assert first.id is not None
    assert first.date_format is None
    assert first.timezone is None

    # Exactly one row was created, and a second call returns the same singleton (idempotent).
    rows = await GlobalPreference.get_list(db=db)
    assert len(rows) == 1

    second = await GlobalPreference.get_global(db=db)
    assert second.uuid == first.uuid
    assert len(await GlobalPreference.get_list(db=db)) == 1


async def test_global_preference_persists_values(db: InfrahubDatabase, default_branch: Branch) -> None:
    obj = await GlobalPreference.get_global(db=db)
    obj.date_format = "yyyy-MM-dd"
    obj.timezone = "UTC"
    await obj.save(db=db)

    reloaded = await GlobalPreference.get_global(db=db)
    assert reloaded.date_format == "yyyy-MM-dd"
    assert reloaded.timezone == "UTC"
    assert len(await GlobalPreference.get_list(db=db)) == 1


async def test_user_preference_get_for_account_none(db: InfrahubDatabase, default_branch: Branch) -> None:
    assert await UserPreference.get_for_account(db=db, account_id="does-not-exist") is None


async def test_user_preference_create_and_lookup(db: InfrahubDatabase, default_branch: Branch) -> None:
    pref = UserPreference(account_id="account-a", date_format="dd/MM/yyyy")
    await pref.create(db=db)

    fetched = await UserPreference.get_for_account(db=db, account_id="account-a")
    assert fetched is not None
    assert fetched.account_id == "account-a"
    assert fetched.date_format == "dd/MM/yyyy"
    assert fetched.timezone is None

    # A different account has no row.
    assert await UserPreference.get_for_account(db=db, account_id="account-b") is None


async def test_user_preference_lookup_is_account_scoped(db: InfrahubDatabase, default_branch: Branch) -> None:
    pref_a = UserPreference(account_id="acc-1", timezone="Europe/Paris")
    await pref_a.create(db=db)
    pref_b = UserPreference(account_id="acc-2", timezone="UTC")
    await pref_b.create(db=db)

    fetched_a = await UserPreference.get_for_account(db=db, account_id="acc-1")
    fetched_b = await UserPreference.get_for_account(db=db, account_id="acc-2")
    assert fetched_a is not None
    assert fetched_b is not None
    assert fetched_a.timezone == "Europe/Paris"
    assert fetched_b.timezone == "UTC"
    assert fetched_a.uuid != fetched_b.uuid
