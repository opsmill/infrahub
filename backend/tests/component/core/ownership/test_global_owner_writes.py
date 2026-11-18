from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.ownership.constants import OWNERS_IDS_FILTER
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_SOURCES_HOLDER,
    HolderKey,
    HolderKind,
    StoredOwnerState,
)
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.resolver import OwnershipResolver
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from tests.helpers.ownership import USER_ID, add_node

SEATS_HOLDER = HolderKey(kind=HolderKind.ATTRIBUTE, attribute="nbr_seats")


@pytest.fixture
async def groups(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, car_person_schema_global: None
) -> list[str]:
    return [
        (await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name)).id
        for name in ("dc-emea", "network-emea", "security")
    ]


async def _stored(db: InfrahubDatabase, branch: Branch, node_id: str, holder: HolderKey) -> StoredOwnerState:
    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[node_id], attributes=True)
    return stored[node_id].get(holder)


async def test_branch_made_before_a_global_owner_change_of_an_attribute_reads_the_new_owner_only(
    db: InfrahubDatabase, default_branch: Branch, groups: list[str]
) -> None:
    person = await add_node(db=db, kind="TestPerson", name="person-a")
    thing = await add_node(db=db, kind="TestCar", name="car-a", nbr_seats=4, is_electric=False, owner=person)
    thing.nbr_seats.owner = groups[0]
    await thing.save(db=db)
    branch = await create_branch(db=db, branch_name="before-global-write")

    thing = await NodeManager.get_one(db=db, id=thing.id, raise_on_error=True)
    thing.nbr_seats.owner = groups[1]
    await thing.save(db=db)

    for read_branch in (default_branch, branch):
        assert await _stored(db, read_branch, thing.id, SEATS_HOLDER) == StoredOwnerState(owner_ids=(groups[1],))
        read = await NodeManager.get_one(
            db=db, branch=read_branch, id=thing.id, include_metadata=MetadataOptions.OWNER, raise_on_error=True
        )
        assert read.nbr_seats.owner_id == groups[1]
    await verify_graph(db=db)


@dataclass
class GlobalWriteTestCase:
    name: str
    holder: HolderKey
    before: StoredOwnerState
    """The state that the global branch stores before the start of the branch, with group indexes as owner IDs."""

    after: StoredOwnerState


GLOBAL_WRITE_TEST_CASES = [
    GlobalWriteTestCase(
        name="node", holder=NODE_HOLDER, before=StoredOwnerState(("0",)), after=StoredOwnerState(("1",))
    ),
    GlobalWriteTestCase(
        name="field_set",
        holder=HolderKey(kind=HolderKind.FIELD_SET, identifier="thing__peer", direction="outbound"),
        before=StoredOwnerState(("0",)),
        after=StoredOwnerState(("1",)),
    ),
    GlobalWriteTestCase(
        name="sources", holder=NODE_SOURCES_HOLDER, before=StoredOwnerState(("0",)), after=StoredOwnerState(("1",))
    ),
    GlobalWriteTestCase(
        name="owners_to_no_owner", holder=NODE_HOLDER, before=StoredOwnerState(("0",)), after=StoredOwnerState(())
    ),
    GlobalWriteTestCase(
        name="no_owner_to_inherit", holder=NODE_HOLDER, before=StoredOwnerState(()), after=StoredOwnerState(None)
    ),
    GlobalWriteTestCase(
        name="template_mark_closed",
        holder=NODE_HOLDER,
        before=StoredOwnerState(("0",), template_id="2"),
        after=StoredOwnerState(("0",)),
    ),
]


def _with_ids(state: StoredOwnerState, groups: list[str]) -> StoredOwnerState:
    return StoredOwnerState(
        owner_ids=None if state.owner_ids is None else tuple(groups[int(index)] for index in state.owner_ids),
        template_id=None if state.template_id is None else groups[int(state.template_id)],
    )


@pytest.mark.parametrize("test_case", GLOBAL_WRITE_TEST_CASES, ids=lambda case: case.name)
async def test_branch_made_before_a_global_write_reads_the_new_state_of_each_holder(
    db: InfrahubDatabase, default_branch: Branch, groups: list[str], test_case: GlobalWriteTestCase
) -> None:
    thing = await add_node(db=db, kind="TestPerson", name="shared-a")
    global_branch = registry.get_global_branch()
    repository = OwnershipRepository(db=db, branch=default_branch, at=None)
    for state in (test_case.before, None, test_case.after):
        if state is None:
            branch = await create_branch(db=db, branch_name="before-global-write")
            continue
        await repository.write(
            node_id=thing.id,
            holder=test_case.holder,
            state=_with_ids(state=state, groups=groups),
            write_branch=global_branch,
            at=Timestamp(),
            user_id=USER_ID,
        )

    expected = _with_ids(state=test_case.after, groups=groups)
    assert await _stored(db, default_branch, thing.id, test_case.holder) == expected
    assert await _stored(db, branch, thing.id, test_case.holder) == expected
    await verify_graph(db=db)


@pytest.mark.parametrize(
    "removed", [StoredOwnerState(("1",)), StoredOwnerState(None)], ids=["owner_replaced", "set_to_inherit"]
)
@pytest.mark.parametrize("added_back", [StoredOwnerState(("0",)), StoredOwnerState(())], ids=["owner", "no_owner"])
async def test_global_write_that_adds_back_a_removed_state_is_read_on_all_branches(
    db: InfrahubDatabase,
    default_branch: Branch,
    groups: list[str],
    removed: StoredOwnerState,
    added_back: StoredOwnerState,
) -> None:
    thing = await add_node(db=db, kind="TestPerson", name="shared-a")
    global_branch = registry.get_global_branch()
    repository = OwnershipRepository(db=db, branch=default_branch, at=None)
    for state in (added_back, None, removed, added_back):
        if state is None:
            branch = await create_branch(db=db, branch_name="before-global-write")
            continue
        await repository.write(
            node_id=thing.id,
            holder=NODE_HOLDER,
            state=_with_ids(state=state, groups=groups),
            write_branch=global_branch,
            at=Timestamp(),
            user_id=USER_ID,
        )

    expected = _with_ids(state=added_back, groups=groups)
    assert await _stored(db, default_branch, thing.id, NODE_HOLDER) == expected
    assert await _stored(db, branch, thing.id, NODE_HOLDER) == expected
    later_branch = await create_branch(db=db, branch_name="after-global-write")
    assert await _stored(db, later_branch, thing.id, NODE_HOLDER) == expected
    await verify_graph(db=db)


async def test_resolver_and_owner_filter_of_a_branch_made_before_a_global_write_give_the_new_owners(
    db: InfrahubDatabase, default_branch: Branch, groups: list[str]
) -> None:
    thing = await add_node(db=db, kind="TestPerson", name="shared-a")
    global_branch = registry.get_global_branch()
    repository = OwnershipRepository(db=db, branch=default_branch, at=None)
    await repository.write(
        node_id=thing.id,
        holder=NODE_HOLDER,
        state=StoredOwnerState((groups[0],)),
        write_branch=global_branch,
        at=Timestamp(),
        user_id=USER_ID,
    )
    branch = await create_branch(db=db, branch_name="before-global-write")
    await repository.write(
        node_id=thing.id,
        holder=NODE_HOLDER,
        state=StoredOwnerState((groups[1],)),
        write_branch=global_branch,
        at=Timestamp(),
        user_id=USER_ID,
    )

    resolver = OwnershipResolver(repository=OwnershipRepository(db=db, branch=branch, at=None))
    resolved = (await resolver.resolve(node_ids=[thing.id]))[thing.id]
    assert resolved.owner_ids == (groups[1],)
    for owner_id, expected in ((groups[0], 0), (groups[1], 1)):
        count = await NodeManager.count(
            db=db, schema="TestPerson", branch=branch, filters={OWNERS_IDS_FILTER: [owner_id]}
        )
        assert count == expected
