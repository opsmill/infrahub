from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import RepositoryObjects
from infrahub.core.manager import NodeManager

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


async def check_repo_correctly_created(repo_id: str, db: InfrahubDatabase, branch_name: str) -> None:
    # Check persons have been correctly loaded
    person_ethan = await NodeManager.get_one_by_default_filter(
        db=db, id="Ethan Carter", kind="TestingPerson", raise_on_error=True, branch=branch_name
    )
    assert person_ethan.name.value == "Ethan Carter"
    assert person_ethan.height.value == 180

    person_olivia = await NodeManager.get_one_by_default_filter(
        db=db, id="Olivia Bennett", kind="TestingPerson", raise_on_error=True, branch=branch_name
    )
    assert person_olivia.name.value == "Olivia Bennett"
    assert person_olivia.height.value == 170

    # Check manufacturers have been correctly loaded
    manufacturer_mercedes = await NodeManager.get_one_by_default_filter(
        db=db,
        id="Mercedes",
        kind="TestingManufacturer",
        raise_on_error=True,
        prefetch_relationships=True,
        branch=branch_name,
    )
    assert manufacturer_mercedes.name.value == "Mercedes"
    assert list((await manufacturer_mercedes.customers.get_peers(db=db)).values())[0].name.value == "Ethan Carter"

    manufacturer_ford = await NodeManager.get_one_by_default_filter(
        db=db,
        id="Ford",
        kind="TestingManufacturer",
        raise_on_error=True,
        prefetch_relationships=True,
        branch=branch_name,
    )
    assert manufacturer_ford.name.value == "Ford"
    assert list((await manufacturer_ford.customers.get_peers(db=db)).values())[0].name.value == "Olivia Bennett"

    # Check repository groups have been correctly created
    repository_group = await NodeManager.get_one_by_default_filter(
        db=db,
        id=f"group-repo-{RepositoryObjects.OBJECT.value}-{repo_id}",
        kind="CoreRepositoryGroup",
        raise_on_error=True,
        prefetch_relationships=True,
        branch=branch_name,
    )
    assert repository_group.content.value == RepositoryObjects.OBJECT.value
    assert (await repository_group.repository.get_peer(db=db)).id == repo_id
    members = (await repository_group.members.get_peers(db=db)).values()
    assert len(members) == 4
    assert {m.id for m in members} == {
        manufacturer_ford.id,
        manufacturer_mercedes.id,
        person_ethan.id,
        person_olivia.id,
    }

    repository_group_menus = await NodeManager.get_one_by_default_filter(
        db=db,
        id=f"group-repo-{RepositoryObjects.MENU.value}-{repo_id}",
        kind="CoreRepositoryGroup",
        raise_on_error=True,
        prefetch_relationships=True,
        branch=branch_name,
    )
    assert repository_group_menus.content.value == RepositoryObjects.MENU.value
    assert (await repository_group_menus.repository.get_peer(db=db)).id == repo_id
    _ = await NodeManager.get_one_by_hfid(
        db=db,
        hfid=["Testing", "Manufacturer"],
        kind="CoreMenu",
        raise_on_error=True,
        prefetch_relationships=True,
        branch=branch_name,
    )
    _ = await NodeManager.get_one_by_hfid(
        db=db,
        hfid=["Testing", "Person"],
        kind="CoreMenu",
        raise_on_error=True,
        prefetch_relationships=True,
        branch=branch_name,
    )
