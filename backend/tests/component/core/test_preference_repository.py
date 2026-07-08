from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.preferences.models import Preference
from infrahub.core.preferences.repository import PreferenceRepository

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_get_for_owner_none_when_absent_and_never_creates(db: InfrahubDatabase, default_branch: Branch) -> None:
    # A missing row means "nothing set": get_for_owner returns None and must NEVER create a row.
    repository = PreferenceRepository(db=db)

    assert await repository.get_for_owner(owner_id="owner-absent") is None
    assert await repository.get_all() == []


async def test_save_then_get_for_owner_round_trip(db: InfrahubDatabase, default_branch: Branch) -> None:
    repository = PreferenceRepository(db=db)
    await repository.save(Preference(owner_id="owner-a", date_format="EU_DATETIME", timezone="Europe/Paris"))

    fetched = await repository.get_for_owner(owner_id="owner-a")
    assert fetched is not None
    assert fetched.owner_id == "owner-a"
    assert fetched.date_format == "EU_DATETIME"
    assert fetched.timezone == "Europe/Paris"


async def test_save_updates_in_place_without_creating_a_second_row(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    repository = PreferenceRepository(db=db)
    await repository.save(Preference(owner_id="owner-a", timezone="Europe/Paris"))

    created = await repository.get_for_owner(owner_id="owner-a")
    assert created is not None

    created.timezone = "UTC"
    await repository.save(created)

    updated = await repository.get_for_owner(owner_id="owner-a")
    assert updated is not None
    assert updated.uuid == created.uuid
    assert updated.timezone == "UTC"
    assert len([p for p in await repository.get_all() if p.owner_id == "owner-a"]) == 1


async def test_get_for_owner_is_owner_scoped(db: InfrahubDatabase, default_branch: Branch) -> None:
    # Owner A's row must never be returned when looking up owner B.
    repository = PreferenceRepository(db=db)
    await repository.save(Preference(owner_id="owner-a", timezone="Europe/Paris"))

    assert await repository.get_for_owner(owner_id="owner-b") is None
    fetched_a = await repository.get_for_owner(owner_id="owner-a")
    assert fetched_a is not None
    assert fetched_a.timezone == "Europe/Paris"


async def test_get_for_owners_returns_map_of_existing_only(db: InfrahubDatabase, default_branch: Branch) -> None:
    repository = PreferenceRepository(db=db)
    await repository.save(Preference(owner_id="owner-a", timezone="Europe/Paris"))
    await repository.save(Preference(owner_id="owner-b", date_format="ISO_DATETIME"))

    result = await repository.get_for_owners(owner_ids={"owner-a", "owner-b", "owner-missing"})
    # Only owners with a row appear in the map; the missing one is simply absent.
    assert set(result) == {"owner-a", "owner-b"}
    assert result["owner-a"].timezone == "Europe/Paris"
    assert result["owner-b"].date_format == "ISO_DATETIME"
