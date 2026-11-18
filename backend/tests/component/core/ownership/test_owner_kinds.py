import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


async def _create(db: InfrahubDatabase, kind: str, **data: str) -> Node:
    node = await Node.init(db=db, schema=kind)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


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
    return await _create(db=db, kind="TestPerson", name="John")


@pytest.fixture
async def repository(db: InfrahubDatabase, register_core_models_schema: SchemaBranch) -> Node:
    return await _create(db=db, kind=InfrahubKind.REPOSITORY, name="repo01", location="git@github.com:user/repo01.git")


async def test_account_and_account_group_are_accepted_as_owner_of_an_attribute_and_of_a_link(
    db: InfrahubDatabase, default_branch: Branch, person: Node
) -> None:
    group = await _create(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")
    account = await _create(db=db, kind=InfrahubKind.ACCOUNT, name="jane", password="a-password")

    car = await _create_car(db=db, person=person, color_owner_id=group.id, link_owner_id=account.id)
    assert await _owner_ids(db=db, branch=default_branch, car_id=car.id) == (group.id, account.id)

    car.color.owner = account
    await car.owner.update(db=db, data={"id": person.id, "_relation__owner": group.id})
    await car.save(db=db)

    assert await _owner_ids(db=db, branch=default_branch, car_id=car.id) == (account.id, group.id)


@pytest.mark.parametrize("holder", ["color_owner_id", "link_owner_id"])
async def test_create_with_a_repository_as_owner_is_refused(
    db: InfrahubDatabase, default_branch: Branch, person: Node, repository: Node, holder: str
) -> None:
    with pytest.raises(ValidationError) as exc:
        await _create_car(db=db, person=person, **{holder: repository.id})

    assert exc.value.message == f"Only an account or an account group can be an owner, not: {repository.id} at owner"
    assert await NodeManager.count(db=db, schema="TestCar", branch=default_branch) == 0


async def test_update_of_an_attribute_owner_to_a_repository_is_refused(
    db: InfrahubDatabase, default_branch: Branch, person: Node, repository: Node
) -> None:
    group = await _create(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")
    car = await _create_car(db=db, person=person, color_owner_id=group.id, link_owner_id=group.id)

    car.color.owner = repository
    with pytest.raises(ValidationError) as exc:
        await car.save(db=db)

    assert exc.value.message == (
        f"Only an account or an account group can be an owner, not: {repository.id} at color.owner"
    )
    assert await _owner_ids(db=db, branch=default_branch, car_id=car.id) == (group.id, group.id)


async def test_update_of_a_link_owner_to_a_repository_is_refused(
    db: InfrahubDatabase, default_branch: Branch, person: Node, repository: Node
) -> None:
    group = await _create(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")
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
    other_person = await _create(db=db, kind="TestPerson", name="Jane")

    await car.owner.update(db=db, data={"id": other_person.id, "_relation__owner": repository.id})
    # The save removes the old link before it writes the new one, so the refusal needs the transaction of a mutation.
    with pytest.raises(ValidationError) as exc:
        async with db.start_transaction() as dbt:
            await car.save(db=dbt)

    assert exc.value.message == (
        f"Only an account or an account group can be an owner, not: {repository.id} at owner.owner"
    )
    stored_car = await NodeManager.get_one(db=db, branch=default_branch, id=car.id, raise_on_error=True)
    assert (await stored_car.owner.get_peer(db=db, raise_on_error=True)).id == person.id
