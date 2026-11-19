import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from tests.helpers.ownership import add_node


async def _create_car(
    db: InfrahubDatabase, person: Node, color_owner_id: str | None = None, link_owner_id: str | None = None
) -> Node:
    car = await Node.init(db=db, schema="TestCar")
    await car.new(
        db=db,
        name="volt",
        color={"value": "#000000", "owner": color_owner_id},
        owner={"id": person.id, "_relation__owner": link_owner_id},
    )
    await car.save(db=db)
    return await NodeManager.get_one(db=db, id=car.id, raise_on_error=True)


async def _owner_ids(db: InfrahubDatabase, branch: Branch, car_id: str) -> tuple[str | None, str | None]:
    """Return the owner of the attribute `color` and the owner of the link to the person, as the database holds them."""
    car = await NodeManager.get_one(
        db=db, branch=branch, id=car_id, include_metadata=MetadataOptions.OWNER, raise_on_error=True
    )
    link = (await car.owner.get_relationships(db=db))[0]
    return car.color.owner_id, link.owner_id


@pytest.fixture
async def person(db: InfrahubDatabase, register_core_models_schema: SchemaBranch, car_person_schema: None) -> Node:
    return await add_node(db=db, kind="TestPerson", name="John")


@pytest.fixture
async def repository(db: InfrahubDatabase, register_core_models_schema: SchemaBranch) -> Node:
    return await add_node(db=db, kind=InfrahubKind.REPOSITORY, name="repo01", location="git@github.com:user/repo01.git")


async def test_account_and_account_group_are_accepted_as_owner_of_an_attribute_and_of_a_link(
    db: InfrahubDatabase, default_branch: Branch, person: Node
) -> None:
    group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")
    account = await add_node(db=db, kind=InfrahubKind.ACCOUNT, name="jane", password="a-password")

    car = await _create_car(db=db, person=person, color_owner_id=group.id, link_owner_id=account.id)
    assert await _owner_ids(db=db, branch=default_branch, car_id=car.id) == (group.id, account.id)

    car.color.owner = account
    await car.owner.update(db=db, data={"id": person.id, "_relation__owner": group.id})
    await car.save(db=db)

    assert await _owner_ids(db=db, branch=default_branch, car_id=car.id) == (account.id, group.id)


async def test_link_given_by_hfid_with_an_owner_is_saved(
    db: InfrahubDatabase, default_branch: Branch, person: Node
) -> None:
    group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")
    other_person = await add_node(db=db, kind="TestPerson", name="Jane")
    car = await _create_car(db=db, person=person)

    await car.owner.update(db=db, data={"hfid": ["Jane"], "_relation__owner": group.id})
    await car.save(db=db)

    stored_car = await NodeManager.get_one(db=db, branch=default_branch, id=car.id, raise_on_error=True)
    assert (await stored_car.owner.get_peer(db=db, raise_on_error=True)).id == other_person.id
    assert await _owner_ids(db=db, branch=default_branch, car_id=car.id) == (None, group.id)


@pytest.mark.parametrize(("holder", "path"), [("color_owner_id", "color.owner"), ("link_owner_id", "owner.owner")])
async def test_create_with_a_repository_as_owner_is_refused(
    db: InfrahubDatabase, default_branch: Branch, person: Node, repository: Node, holder: str, path: str
) -> None:
    with pytest.raises(ValidationError) as exc:
        await _create_car(db=db, person=person, **{holder: repository.id})

    assert exc.value.message == f"Only an account or an account group can be an owner, not: {repository.id} at {path}"
    assert await NodeManager.count(db=db, schema="TestCar", branch=default_branch) == 0


async def test_update_of_an_attribute_owner_to_a_repository_is_refused(
    db: InfrahubDatabase, default_branch: Branch, person: Node, repository: Node
) -> None:
    group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")
    car = await _create_car(db=db, person=person, color_owner_id=group.id, link_owner_id=group.id)

    car.color.owner = repository
    with pytest.raises(ValidationError) as exc:
        await car.save(db=db)

    assert exc.value.message == (
        f"Only an account or an account group can be an owner, not: {repository.id} at color.owner"
    )
    assert await _owner_ids(db=db, branch=default_branch, car_id=car.id) == (group.id, group.id)


async def test_refused_owner_of_one_field_stops_the_writes_of_the_other_fields(
    db: InfrahubDatabase, default_branch: Branch, person: Node, repository: Node
) -> None:
    group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")
    account = await add_node(db=db, kind=InfrahubKind.ACCOUNT, name="jane", password="a-password")
    car = await _create_car(db=db, person=person, color_owner_id=group.id, link_owner_id=group.id)
    car.name.value = "bolt"
    car.name.owner = account
    car.color.owner = repository

    with pytest.raises(ValidationError) as exc:
        await car.save(db=db)

    assert exc.value.message == (
        f"Only an account or an account group can be an owner, not: {repository.id} at color.owner"
    )
    stored_car = await NodeManager.get_one(
        db=db, branch=default_branch, id=car.id, include_metadata=MetadataOptions.OWNER, raise_on_error=True
    )
    assert (stored_car.name.value, stored_car.name.owner_id, stored_car.color.owner_id) == ("volt", None, group.id)
    result = await db.execute_query(
        query="MATCH ()-[edge:HAS_OWNER]->(:Node {uuid: $account_id}) RETURN count(edge) AS edges",
        params={"account_id": account.id},
    )
    assert result[0]["edges"] == 0


async def test_update_of_a_link_owner_to_a_repository_is_refused(
    db: InfrahubDatabase, default_branch: Branch, person: Node, repository: Node
) -> None:
    group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")
    car = await _create_car(db=db, person=person, color_owner_id=group.id, link_owner_id=group.id)

    await car.owner.update(db=db, data={"id": person.id, "_relation__owner": repository.id})
    with pytest.raises(ValidationError) as exc:
        await car.save(db=db)

    assert exc.value.message == (
        f"Only an account or an account group can be an owner, not: {repository.id} at owner.owner"
    )
    assert await _owner_ids(db=db, branch=default_branch, car_id=car.id) == (group.id, group.id)


async def test_new_link_with_a_repository_as_owner_is_refused_on_an_existing_node(
    db: InfrahubDatabase, default_branch: Branch, person: Node, repository: Node
) -> None:
    car = await _create_car(db=db, person=person)
    other_person = await add_node(db=db, kind="TestPerson", name="Jane")

    await car.owner.update(db=db, data={"id": other_person.id, "_relation__owner": repository.id})
    with pytest.raises(ValidationError) as exc:
        await car.save(db=db)

    assert exc.value.message == (
        f"Only an account or an account group can be an owner, not: {repository.id} at owner.owner"
    )
    stored_car = await NodeManager.get_one(db=db, branch=default_branch, id=car.id, raise_on_error=True)
    assert (await stored_car.owner.get_peer(db=db, raise_on_error=True)).id == person.id
