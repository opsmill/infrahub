from dataclasses import dataclass

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.ownership.constants import NO_OWNER_VERTEX_UUID
from infrahub.core.ownership.models import NODE_HOLDER, NODE_SOURCES_HOLDER, HolderKey, StoredOwnerState
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.query import QueryType
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from infrahub.exceptions import QueryError
from tests.helpers.ownership import USER_ID, create_groups, set_owners


async def _create_person(db: InfrahubDatabase, name: str) -> Node:
    person = await Node.init(db=db, schema="TestPerson")
    await person.new(db=db, name=name)
    await person.save(db=db)
    return person


async def _read(
    db: InfrahubDatabase, branch: Branch, node_id: str, at: Timestamp | None = None, holder: HolderKey = NODE_HOLDER
) -> StoredOwnerState:
    stored = await OwnershipRepository(db=db, branch=branch, at=at).read(node_ids=[node_id])
    assert list(stored) == [node_id]
    return stored[node_id].get(holder)


def _owner_ids(group_ids: dict[str, str], names: tuple[str, ...] | None) -> tuple[str, ...] | None:
    return None if names is None else tuple(sorted(group_ids[name] for name in names))


@dataclass
class BranchWriteTestCase:
    name: str
    default_branch_owners: tuple[str, ...] | None
    """Group names, written before the branch starts. None is inherit, an empty tuple is "no owner"."""

    branch_owners: tuple[str, ...] | None


BRANCH_WRITE_TEST_CASES: list[BranchWriteTestCase] = [
    BranchWriteTestCase(
        name="owners_over_inherit", default_branch_owners=None, branch_owners=("dc-emea", "network-emea")
    ),
    BranchWriteTestCase(
        name="owners_over_other_owners",
        default_branch_owners=("dc-emea", "network-emea"),
        branch_owners=("network-emea", "security"),
    ),
    BranchWriteTestCase(name="owners_over_no_owner", default_branch_owners=(), branch_owners=("security",)),
    BranchWriteTestCase(name="no_owner_over_inherit", default_branch_owners=None, branch_owners=()),
    BranchWriteTestCase(
        name="no_owner_over_owners", default_branch_owners=("dc-emea", "network-emea"), branch_owners=()
    ),
    BranchWriteTestCase(name="inherit_over_owners", default_branch_owners=("dc-emea",), branch_owners=None),
    BranchWriteTestCase(name="inherit_over_no_owner", default_branch_owners=(), branch_owners=None),
]


@dataclass
class BranchWriteDataset:
    branch: Branch
    group_ids: dict[str, str]
    person_ids: dict[str, str]
    """The person of each test case, by test case name."""


class TestOwnerStateOnBranch:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        car_person_schema_scope_class: SchemaBranch,
    ) -> BranchWriteDataset:
        group_ids = await create_groups(db=db)
        person_ids: dict[str, str] = {}
        for test_case in BRANCH_WRITE_TEST_CASES:
            person = await _create_person(db=db, name=test_case.name)
            person_ids[test_case.name] = person.id
            if test_case.default_branch_owners is not None:
                await set_owners(
                    db=db,
                    branch=default_branch_scope_class,
                    node_id=person.id,
                    owner_ids=_owner_ids(group_ids=group_ids, names=test_case.default_branch_owners),
                )
        branch = await create_branch(branch_name="branch2", db=db)
        return BranchWriteDataset(branch=branch, group_ids=group_ids, person_ids=person_ids)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in BRANCH_WRITE_TEST_CASES])
    async def test_state_set_on_branch_stays_on_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        dataset: BranchWriteDataset,
        test_case: BranchWriteTestCase,
    ) -> None:
        person_id = dataset.person_ids[test_case.name]
        before = StoredOwnerState(
            owner_ids=_owner_ids(group_ids=dataset.group_ids, names=test_case.default_branch_owners)
        )
        after = StoredOwnerState(owner_ids=_owner_ids(group_ids=dataset.group_ids, names=test_case.branch_owners))
        assert await _read(db=db, branch=dataset.branch, node_id=person_id) == before

        await set_owners(db=db, branch=dataset.branch, node_id=person_id, owner_ids=after.owner_ids)

        assert await _read(db=db, branch=dataset.branch, node_id=person_id) == after
        assert await _read(db=db, branch=default_branch_scope_class, node_id=person_id) == before

    async def test_graph_stays_valid_after_the_writes(self, db: InfrahubDatabase, dataset: BranchWriteDataset) -> None:
        await verify_graph(db=db, kinds=["TestPerson"])


async def test_each_state_on_default_branch_at_each_time(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    group_ids = await create_groups(db=db)
    owners = _owner_ids(group_ids=group_ids, names=("dc-emea", "network-emea"))
    person = await _create_person(db=db, name="John")
    other_person = await _create_person(db=db, name="Jane")
    created_at = Timestamp()
    assert (await _read(db=db, branch=default_branch, node_id=person.id)).owner_ids is None

    owners_at = Timestamp()
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=owners, at=owners_at)
    assert await _read(db=db, branch=default_branch, node_id=person.id) == StoredOwnerState(owner_ids=owners)

    no_owner_at = Timestamp()
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=(), at=no_owner_at)
    assert await _read(db=db, branch=default_branch, node_id=person.id) == StoredOwnerState(owner_ids=())

    inherit_at = Timestamp()
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=None, at=inherit_at)
    assert await _read(db=db, branch=default_branch, node_id=person.id) == StoredOwnerState(owner_ids=None)

    assert await _read(db=db, branch=default_branch, node_id=person.id, at=created_at) == StoredOwnerState(
        owner_ids=None
    )
    assert await _read(db=db, branch=default_branch, node_id=person.id, at=owners_at) == StoredOwnerState(
        owner_ids=owners
    )
    assert await _read(db=db, branch=default_branch, node_id=person.id, at=no_owner_at) == StoredOwnerState(
        owner_ids=()
    )
    assert (await _read(db=db, branch=default_branch, node_id=other_person.id)).owner_ids is None


async def test_read_returns_only_active_nodes(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    person = await _create_person(db=db, name="John")
    deleted_person = await _create_person(db=db, name="Jane")
    await deleted_person.delete(db=db)

    stored = await OwnershipRepository(db=db, branch=default_branch, at=None).read(
        node_ids=[person.id, deleted_person.id, "unknown-id"]
    )

    assert list(stored) == [person.id]
    assert stored[person.id].kind == "TestPerson"
    assert stored[person.id].holders == {}


async def _owner_edges(db: InfrahubDatabase, node_id: str) -> list[tuple[str, str, str, bool]]:
    """Return the peer ID, the branch, the status and the open state of each owner edge that starts at the node."""
    rows = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[r:HAS_OWNER|HAS_NO_OWNER]->(peer)
        RETURN peer.uuid AS peer_id, r.branch AS branch, r.status AS status, r.to IS NULL AS is_open
        """,
        params={"node_id": node_id},
        name="test_read_owner_edges",
        type=QueryType.READ,
    )
    return sorted((row["peer_id"], row["branch"], row["status"], row["is_open"]) for row in rows)


async def test_node_delete_closes_owner_edges_of_the_node_and_keeps_edges_to_the_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    group_ids = await create_groups(db=db)
    owners = _owner_ids(group_ids=group_ids, names=("dc-emea", "security"))
    person = await _create_person(db=db, name="John")
    other_person = await _create_person(db=db, name="Jane")
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=owners)
    await set_owners(db=db, branch=default_branch, node_id=other_person.id, owner_ids=owners)
    await set_owners(db=db, branch=default_branch, node_id=group_ids["security"], owner_ids=(group_ids["dc-emea"],))
    assert await _owner_edges(db=db, node_id=person.id) == [
        (owner_id, default_branch.name, "active", True) for owner_id in owners
    ]

    await person.delete(db=db)
    group = await NodeManager.get_one(db=db, branch=default_branch, id=group_ids["security"], raise_on_error=True)
    await group.delete(db=db)

    assert await _owner_edges(db=db, node_id=person.id) == [
        (owner_id, default_branch.name, "active", False) for owner_id in owners
    ]
    assert await _owner_edges(db=db, node_id=group_ids["security"]) == [
        (group_ids["dc-emea"], GLOBAL_BRANCH_NAME, "active", False),
        (group_ids["dc-emea"], GLOBAL_BRANCH_NAME, "deleted", True),
    ]
    assert await _read(db=db, branch=default_branch, node_id=other_person.id) == StoredOwnerState(owner_ids=owners)
    await verify_graph(db=db, kinds=["TestPerson", InfrahubKind.ACCOUNTGROUP])


async def test_node_delete_on_branch_hides_owner_edges_on_that_branch_only(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    group_ids = await create_groups(db=db)
    person = await _create_person(db=db, name="John")
    no_owner_person = await _create_person(db=db, name="Jane")
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=(group_ids["security"],))
    await set_owners(db=db, branch=default_branch, node_id=no_owner_person.id, owner_ids=())
    branch = await create_branch(branch_name="branch2", db=db)

    for node_id in (person.id, no_owner_person.id):
        node = await NodeManager.get_one(db=db, branch=branch, id=node_id, raise_on_error=True)
        await node.delete(db=db)

    assert await _owner_edges(db=db, node_id=person.id) == [
        (group_ids["security"], "branch2", "deleted", True),
        (group_ids["security"], default_branch.name, "active", True),
    ]
    assert await _owner_edges(db=db, node_id=no_owner_person.id) == [
        (NO_OWNER_VERTEX_UUID, "branch2", "deleted", True),
        (NO_OWNER_VERTEX_UUID, default_branch.name, "active", True),
    ]
    assert await _read(db=db, branch=default_branch, node_id=person.id) == StoredOwnerState(
        owner_ids=(group_ids["security"],)
    )
    assert await _read(db=db, branch=default_branch, node_id=no_owner_person.id) == StoredOwnerState(owner_ids=())
    await verify_graph(db=db, kinds=["TestPerson"])


@pytest.mark.parametrize("holder", [NODE_HOLDER, NODE_SOURCES_HOLDER], ids=["owners", "sources"])
async def test_branch_removes_an_owner_that_the_default_branch_deleted_before_the_start_of_the_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    holder: HolderKey,
) -> None:
    group_ids = await create_groups(db=db)
    person = await _create_person(db=db, name="John")
    await set_owners(
        db=db,
        branch=default_branch,
        node_id=person.id,
        owner_ids=_owner_ids(group_ids=group_ids, names=("dc-emea", "security")),
        holder=holder,
    )
    group = await NodeManager.get_one(db=db, branch=default_branch, id=group_ids["security"], raise_on_error=True)
    await group.delete(db=db)
    branch = await create_branch(branch_name="branch2", db=db)

    await set_owners(db=db, branch=branch, node_id=person.id, owner_ids=(group_ids["dc-emea"],), holder=holder)

    assert await _read(db=db, branch=branch, node_id=person.id, holder=holder) == StoredOwnerState(
        owner_ids=(group_ids["dc-emea"],)
    )
    await verify_graph(db=db, kinds=["TestPerson", InfrahubKind.ACCOUNTGROUP])


async def test_delete_of_a_node_with_a_source_on_an_attribute_closes_the_sources_of_the_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    group_ids = await create_groups(db=db)
    person = await _create_person(db=db, name="John")
    await set_owners(
        db=db,
        branch=default_branch,
        node_id=person.id,
        owner_ids=_owner_ids(group_ids=group_ids, names=("dc-emea",)),
        holder=NODE_SOURCES_HOLDER,
    )
    person = await NodeManager.get_one(db=db, branch=default_branch, id=person.id, raise_on_error=True)
    person.name.source = group_ids["dc-emea"]
    await person.save(db=db)

    await person.delete(db=db)

    records = await db.execute_query(
        query="""
MATCH (:Node {uuid: $node_id})-[r:HAS_SOURCE]->(:Node)
WHERE r.status = "active" AND r.to IS NULL
RETURN count(r) AS open_edges
""",
        params={"node_id": person.id},
    )
    assert records[0]["open_edges"] == 0
    await verify_graph(db=db)


async def test_write_on_node_that_is_not_active_raises(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    group_ids = await create_groups(db=db)
    person = await _create_person(db=db, name="John")
    await person.delete(db=db)
    repository = OwnershipRepository(db=db, branch=default_branch, at=None)

    with pytest.raises(QueryError):
        await repository.write(
            node_id=person.id,
            holder=NODE_HOLDER,
            state=StoredOwnerState(owner_ids=(group_ids["security"],)),
            write_branch=default_branch,
            at=Timestamp(),
            user_id=USER_ID,
        )

    records = await db.execute_query(
        query="MATCH (:Node {uuid: $node_id})-[r:HAS_OWNER]->() RETURN count(r) AS edges", params={"node_id": person.id}
    )
    assert records[0]["edges"] == 0


async def test_owner_edges_win_over_no_owner_edge(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    group_ids = await create_groups(db=db)
    person = await _create_person(db=db, name="John")
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=(group_ids["security"],))
    await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $node_id})
        MERGE (no_owner:NoOwner {uuid: $no_owner_uuid})
        CREATE (n)-[:HAS_NO_OWNER {branch: $branch, branch_level: 1, status: "active", from: $at}]->(no_owner)
        """,
        params={
            "node_id": person.id,
            "no_owner_uuid": NO_OWNER_VERTEX_UUID,
            "branch": default_branch.name,
            "at": Timestamp().to_string(),
        },
        name="test_add_no_owner_edge",
        type=QueryType.WRITE,
    )

    assert await _read(db=db, branch=default_branch, node_id=person.id) == StoredOwnerState(
        owner_ids=(group_ids["security"],)
    )


async def test_write_on_branch_hides_inherited_edge_to_an_owner_that_the_branch_also_added(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    group_ids = await create_groups(db=db)
    owners = (group_ids["security"],)
    person = await _create_person(db=db, name="John")
    branch = await create_branch(branch_name="branch2", db=db)
    await set_owners(db=db, branch=default_branch, node_id=person.id, owner_ids=owners)
    await set_owners(db=db, branch=branch, node_id=person.id, owner_ids=owners)
    await branch.rebase(db=db)
    assert await _read(db=db, branch=branch, node_id=person.id) == StoredOwnerState(owner_ids=owners)

    await set_owners(db=db, branch=branch, node_id=person.id, owner_ids=None)

    assert await _read(db=db, branch=branch, node_id=person.id) == StoredOwnerState(owner_ids=None)
    assert await _read(db=db, branch=default_branch, node_id=person.id) == StoredOwnerState(owner_ids=owners)


async def test_write_on_branch_for_node_that_all_branches_share_reads_back_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    group_ids = await create_groups(db=db)
    owners = (group_ids["security"],)
    branch = await create_branch(branch_name="branch2", db=db)

    await set_owners(db=db, branch=branch, node_id=group_ids["dc-emea"], owner_ids=owners)

    assert await _read(db=db, branch=branch, node_id=group_ids["dc-emea"]) == StoredOwnerState(owner_ids=owners)
    assert await _read(db=db, branch=default_branch, node_id=group_ids["dc-emea"]) == StoredOwnerState(owner_ids=owners)


async def test_write_follows_the_transaction_of_the_caller(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    group_ids = await create_groups(db=db)
    person = await _create_person(db=db, name="John")

    with pytest.raises(RuntimeError, match=r"^roll back$"):
        async with db.start_transaction() as dbt:
            await set_owners(db=dbt, branch=default_branch, node_id=person.id, owner_ids=(group_ids["security"],))
            assert (await _read(db=dbt, branch=default_branch, node_id=person.id)).owner_ids == (group_ids["security"],)
            raise RuntimeError("roll back")

    assert (await _read(db=db, branch=default_branch, node_id=person.id)).owner_ids is None
