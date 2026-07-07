from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.preferences.models import Preference

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_get_for_owner_none_when_absent_and_never_creates(db: InfrahubDatabase, default_branch: Branch) -> None:
    # A missing row means "nothing set": get_for_owner returns None and must NEVER create a row.
    assert await Preference.get_for_owner(db=db, owner_id="owner-absent") is None
    assert await Preference.get_list(db=db) == []


async def test_create_and_get_for_owner_round_trip(db: InfrahubDatabase, default_branch: Branch) -> None:
    pref = Preference(owner_id="owner-a", date_format="EU_DATETIME", timezone="Europe/Paris")
    await pref.create(db=db)

    fetched = await Preference.get_for_owner(db=db, owner_id="owner-a")
    assert fetched is not None
    assert fetched.owner_id == "owner-a"
    assert fetched.date_format == "EU_DATETIME"
    assert fetched.timezone == "Europe/Paris"


async def test_get_for_owner_is_owner_scoped(db: InfrahubDatabase, default_branch: Branch) -> None:
    # Owner A's row must never be returned when looking up owner B.
    await Preference(owner_id="owner-a", timezone="Europe/Paris").create(db=db)

    assert await Preference.get_for_owner(db=db, owner_id="owner-b") is None
    fetched_a = await Preference.get_for_owner(db=db, owner_id="owner-a")
    assert fetched_a is not None
    assert fetched_a.timezone == "Europe/Paris"


async def test_get_for_owners_returns_map_of_existing_only(db: InfrahubDatabase, default_branch: Branch) -> None:
    await Preference(owner_id="owner-a", timezone="Europe/Paris").create(db=db)
    await Preference(owner_id="owner-b", date_format="ISO_DATETIME").create(db=db)

    result = await Preference.get_for_owners(db=db, owner_ids={"owner-a", "owner-b", "owner-missing"})
    # Only owners with a row appear in the map; the missing one is simply absent.
    assert set(result) == {"owner-a", "owner-b"}
    assert result["owner-a"].timezone == "Europe/Paris"
    assert result["owner-b"].date_format == "ISO_DATETIME"


async def test_date_format_rejects_unknown_key() -> None:
    # date_format is enum-typed, so constructing with a non-DateFormat key must raise. The match
    # is anchored and stops before pydantic's trailing documentation URL, which carries the
    # installed pydantic version.
    with pytest.raises(
        ValueError,
        match=(
            r"^1 validation error for Preference\n"
            r"date_format\n"
            r"  Input should be 'ISO_8601', 'ISO_DATETIME', 'ISO_DATETIME_SECONDS', 'EU_DATETIME' or 'US_12H' "
            r"\[type=enum, input_value='NOPE', input_type=str\]"
        ),
    ):
        Preference(owner_id="owner-a", date_format="NOPE")


async def test_date_format_accepts_valid_key() -> None:
    pref = Preference(owner_id="owner-a", date_format="ISO_DATETIME")
    assert pref.date_format == "ISO_DATETIME"
