import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.ownership.constants import SOURCES_IDS_FILTER
from infrahub.core.ownership.models import INHERIT, NODE_SOURCES_HOLDER, HolderKey, HolderKind, StoredOwnerState
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from tests.helpers.ownership import USER_ID, add_node

NAME_HOLDER = HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name")


async def _write(
    db: InfrahubDatabase, branch: Branch, node_id: str, holder: HolderKey, owner_ids: tuple[str, ...] | None
) -> None:
    await OwnershipRepository(db=db, branch=branch, at=None).write(
        node_id=node_id,
        holder=holder,
        state=StoredOwnerState(owner_ids=owner_ids),
        write_branch=branch,
        at=Timestamp(),
        user_id=USER_ID,
    )


async def _stored(db: InfrahubDatabase, branch: Branch, node_id: str, holder: HolderKey) -> StoredOwnerState:
    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[node_id], attributes=True)
    return stored[node_id].get(holder)


async def _single_owner_id(db: InfrahubDatabase, branch: Branch, node_id: str) -> str | None:
    person = await NodeManager.get_one(
        db=db, branch=branch, id=node_id, include_metadata=MetadataOptions.OWNER, raise_on_error=True
    )
    return person.name.owner_id


@pytest.fixture
async def groups(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, car_person_schema: None
) -> list[str]:
    return sorted(
        [
            (await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name)).id
            for name in ("dc-emea", "network-emea", "security")
        ]
    )


async def test_attribute_gives_a_single_owner_only_when_it_has_exactly_one_own_owner(
    db: InfrahubDatabase, default_branch: Branch, groups: list[str]
) -> None:
    person = await add_node(db=db, kind="TestPerson", name="John")

    await _write(db=db, branch=default_branch, node_id=person.id, holder=NAME_HOLDER, owner_ids=tuple(groups[:2]))
    assert await _stored(db, default_branch, person.id, NAME_HOLDER) == StoredOwnerState(owner_ids=tuple(groups[:2]))
    assert await _single_owner_id(db, default_branch, person.id) is None

    await _write(db=db, branch=default_branch, node_id=person.id, holder=NAME_HOLDER, owner_ids=(groups[2],))
    assert await _single_owner_id(db, default_branch, person.id) == groups[2]

    await _write(db=db, branch=default_branch, node_id=person.id, holder=NAME_HOLDER, owner_ids=())
    assert await _stored(db, default_branch, person.id, NAME_HOLDER) == StoredOwnerState(owner_ids=())
    assert await _single_owner_id(db, default_branch, person.id) is None
    await verify_graph(db=db)


async def test_write_of_the_single_owner_replaces_all_own_owners_and_a_clear_sets_the_attribute_to_inherit(
    db: InfrahubDatabase, default_branch: Branch, groups: list[str]
) -> None:
    person = await add_node(db=db, kind="TestPerson", name="John")
    await _write(db=db, branch=default_branch, node_id=person.id, holder=NAME_HOLDER, owner_ids=tuple(groups[:2]))

    person = await NodeManager.get_one(db=db, id=person.id, raise_on_error=True)
    person.name.owner = groups[2]
    await person.save(db=db)
    assert await _stored(db, default_branch, person.id, NAME_HOLDER) == StoredOwnerState(owner_ids=(groups[2],))
    assert await _single_owner_id(db, default_branch, person.id) == groups[2]

    person = await NodeManager.get_one(db=db, id=person.id, include_metadata=MetadataOptions.OWNER, raise_on_error=True)
    person.name.clear_owner()
    await person.save(db=db)
    assert await _stored(db, default_branch, person.id, NAME_HOLDER) == INHERIT
    assert await _single_owner_id(db, default_branch, person.id) is None
    await verify_graph(db=db)


async def test_write_of_the_single_owner_on_a_branch_hides_the_owners_of_the_default_branch_on_that_branch_only(
    db: InfrahubDatabase, default_branch: Branch, groups: list[str]
) -> None:
    person = await add_node(db=db, kind="TestPerson", name="John")
    await _write(db=db, branch=default_branch, node_id=person.id, holder=NAME_HOLDER, owner_ids=tuple(groups[:2]))
    branch = await create_branch(branch_name="branch2", db=db)

    person_on_branch = await NodeManager.get_one(db=db, branch=branch, id=person.id, raise_on_error=True)
    person_on_branch.name.owner = groups[2]
    await person_on_branch.save(db=db)

    assert await _stored(db, branch, person.id, NAME_HOLDER) == StoredOwnerState(owner_ids=(groups[2],))
    assert await _single_owner_id(db, branch, person.id) == groups[2]
    assert await _stored(db, default_branch, person.id, NAME_HOLDER) == StoredOwnerState(owner_ids=tuple(groups[:2]))
    assert await _single_owner_id(db, default_branch, person.id) is None
    await verify_graph(db=db)


async def test_sources_of_a_node_are_stored_and_filter_the_list_before_pagination(
    db: InfrahubDatabase, default_branch: Branch, groups: list[str]
) -> None:
    persons = [await add_node(db=db, kind="TestPerson", name=f"person-{index}") for index in range(4)]
    for person in persons[:3]:
        await _write(
            db=db, branch=default_branch, node_id=person.id, holder=NODE_SOURCES_HOLDER, owner_ids=tuple(groups[:2])
        )
    await _write(db=db, branch=default_branch, node_id=persons[2].id, holder=NODE_SOURCES_HOLDER, owner_ids=None)
    branch = await create_branch(branch_name="branch2", db=db)
    await _write(db=db, branch=branch, node_id=persons[3].id, holder=NODE_SOURCES_HOLDER, owner_ids=(groups[0],))

    assert await _stored(db, default_branch, persons[0].id, NODE_SOURCES_HOLDER) == StoredOwnerState(
        owner_ids=tuple(groups[:2])
    )
    assert await _stored(db, default_branch, persons[2].id, NODE_SOURCES_HOLDER) == INHERIT

    filters = {SOURCES_IDS_FILTER: groups[:2]}
    pages = [
        await NodeManager.query(
            db=db, schema="TestPerson", branch=default_branch, filters=filters, limit=1, offset=offset
        )
        for offset in range(3)
    ]
    assert [[node.id for node in page] for page in pages] == [[persons[0].id], [persons[1].id], []]
    assert await NodeManager.count(db=db, schema="TestPerson", branch=default_branch, filters=filters) == 2
    assert await NodeManager.count(db=db, schema="TestPerson", branch=branch, filters=filters) == 3
    assert (
        await NodeManager.count(
            db=db, schema="TestPerson", branch=default_branch, filters={SOURCES_IDS_FILTER: [groups[2]]}
        )
        == 0
    )
    await verify_graph(db=db)
