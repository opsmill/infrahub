import asyncio

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.ownership.models import NODE_HOLDER, HolderKey, StoredOwnerState, field_holder
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import GraphCheck, collect_graph_violations, verify_graph
from infrahub.exceptions import QueryError
from tests.helpers.ownership import USER_ID, read_owners

SECONDS_BEFORE_FIRST_COMMIT = 1.0


@pytest.fixture
async def group_ids(db: InfrahubDatabase, register_core_models_schema: SchemaBranch) -> list[str]:
    ids: list[str] = []
    for name in ("dc-emea", "network-emea"):
        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name=name)
        await group.save(db=db)
        ids.append(group.id)
    return ids


@pytest.fixture
async def person(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> Node:
    node = await Node.init(db=db, schema="TestPerson")
    await node.new(db=db, name="John")
    await node.save(db=db)
    return node


def _holder(default_branch: Branch, field_name: str) -> HolderKey:
    schema = registry.schema.get(name="TestPerson", branch=default_branch, duplicate=False)
    holder = field_holder(schema=schema, field_name=field_name)
    assert holder is not None
    return holder


async def _write(db: InfrahubDatabase, branch: Branch, node_id: str, holder: HolderKey, owner_ids: list[str]) -> None:
    await OwnershipRepository(db=db, branch=branch, at=None).write(
        node_id=node_id,
        holder=holder,
        state=StoredOwnerState(owner_ids=tuple(owner_ids)),
        write_branch=branch,
        at=Timestamp(),
        user_id=USER_ID,
    )


async def _count_field_sets(db: InfrahubDatabase, node_id: str) -> int:
    records = await db.execute_query(
        query="MATCH (:Node {uuid: $node_id})-[:HAS_OWNER_SET]->(s:OwnerSet) RETURN count(DISTINCT s) AS sets",
        params={"node_id": node_id},
    )
    return records[0]["sets"]


async def test_two_first_writes_in_open_transactions_create_one_set(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    holder = _holder(default_branch=default_branch, field_name="cars")
    first_is_written = asyncio.Event()

    async def first_write() -> None:
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            await _write(db=dbt, branch=default_branch, node_id=person.id, holder=holder, owner_ids=group_ids[:1])
            first_is_written.set()
            # The second write runs while this transaction is open.
            await asyncio.sleep(SECONDS_BEFORE_FIRST_COMMIT)

    async def second_write() -> None:
        await first_is_written.wait()
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            await _write(db=dbt, branch=default_branch, node_id=person.id, holder=holder, owner_ids=group_ids[1:])

    await asyncio.gather(first_write(), second_write())

    assert await _count_field_sets(db=db, node_id=person.id) == 1
    assert await read_owners(db=db, branch=default_branch, node_id=person.id, holder=holder) == tuple(group_ids[1:])


async def test_two_writes_of_one_owner_in_open_transactions_create_one_edge(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    branch = await create_branch(db=db, branch_name="two-writes")
    first_is_written = asyncio.Event()

    async def first_write() -> None:
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            await _write(db=dbt, branch=branch, node_id=person.id, holder=NODE_HOLDER, owner_ids=group_ids[:1])
            first_is_written.set()
            # The second write runs while this transaction is open.
            await asyncio.sleep(SECONDS_BEFORE_FIRST_COMMIT)

    async def second_write() -> None:
        await first_is_written.wait()
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            await _write(db=dbt, branch=branch, node_id=person.id, holder=NODE_HOLDER, owner_ids=group_ids[:1])

    await asyncio.gather(first_write(), second_write())

    records = await db.execute_query(
        query="""
MATCH ()-[r:HAS_OWNER {branch: $branch, status: "active"}]->(:Node {uuid: $owner_id})
WHERE r.to IS NULL
RETURN count(r) AS edges
""",
        params={"branch": branch.name, "owner_id": group_ids[0]},
    )
    assert records[0]["edges"] == 1
    assert await read_owners(db=db, branch=branch, node_id=person.id, holder=NODE_HOLDER) == tuple(group_ids[:1])


async def test_write_reuses_a_set_that_has_another_property(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    holder = _holder(default_branch=default_branch, field_name="cars")
    await _write(db=db, branch=default_branch, node_id=person.id, holder=holder, owner_ids=group_ids[:1])
    await db.execute_query(query='MATCH (s:OwnerSet) SET s.note = "not part of the key"')

    await _write(db=db, branch=default_branch, node_id=person.id, holder=holder, owner_ids=group_ids[1:])

    assert await _count_field_sets(db=db, node_id=person.id) == 1
    assert await read_owners(db=db, branch=default_branch, node_id=person.id, holder=holder) == tuple(group_ids[1:])


async def test_graph_validation_reports_two_sets_with_the_same_key(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    holder = _holder(default_branch=default_branch, field_name="cars")
    await _write(db=db, branch=default_branch, node_id=person.id, holder=holder, owner_ids=group_ids[:1])
    await verify_graph(db=db, kinds=["TestPerson"])

    await db.execute_query(
        query="""
MATCH (n:Node {uuid: $node_id})-[e:HAS_OWNER_SET]->(s:OwnerSet)
CREATE (n)-[copy:HAS_OWNER_SET]->(duplicate:OwnerSet)
SET duplicate = properties(s), copy = properties(e)
""",
        params={"node_id": person.id},
    )

    violations = await collect_graph_violations(db=db, kinds=["TestPerson"])
    assert [violation.check for violation in violations] == [GraphCheck.DUPLICATE_OWNER_SETS]
    assert person.id in violations[0].message


async def test_node_delete_closes_each_owner_edge_of_its_attributes_and_sets(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    for field_name in ("name", "cars"):
        await _write(
            db=db,
            branch=default_branch,
            node_id=person.id,
            holder=_holder(default_branch=default_branch, field_name=field_name),
            owner_ids=group_ids,
        )

    await person.delete(db=db)

    records = await db.execute_query(
        query="""
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE|HAS_OWNER_SET]->(holder)-[r:HAS_OWNER]->(:Node)
WHERE r.status = "active" AND r.to IS NULL
RETURN count(r) AS open_edges
""",
        params={"node_id": person.id},
    )
    assert records[0]["open_edges"] == 0
    await verify_graph(db=db, kinds=["TestPerson"])


@pytest.mark.parametrize(
    ("field_name", "on_branch", "delete_first"),
    [
        *[
            pytest.param(field_name, on_branch, False, id=f"write-first-{branch_id}-{field_name or 'node'}")
            for branch_id, on_branch in (("default-branch", False), ("branch", True))
            for field_name in (None, "name", "cars")
        ],
        # A write after the delete fails its check that the node is active before it reads the holder.
        pytest.param(None, False, True, id="delete-first-default-branch-node"),
        pytest.param(None, True, True, id="delete-first-branch-node"),
    ],
)
async def test_owner_write_and_node_delete_in_open_transactions_leave_no_open_owner_edge(
    db: InfrahubDatabase,
    default_branch: Branch,
    person: Node,
    group_ids: list[str],
    field_name: str | None,
    on_branch: bool,
    delete_first: bool,
) -> None:
    branch = await create_branch(db=db, branch_name="write-and-delete") if on_branch else default_branch
    holder = _holder(default_branch=default_branch, field_name=field_name) if field_name else NODE_HOLDER
    first_is_done = asyncio.Event()

    async def write_owners() -> None:
        if delete_first:
            await first_is_done.wait()
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            if delete_first:
                with pytest.raises(QueryError):
                    await _write(db=dbt, branch=branch, node_id=person.id, holder=holder, owner_ids=group_ids[:1])
            else:
                await _write(db=dbt, branch=branch, node_id=person.id, holder=holder, owner_ids=group_ids[:1])
                first_is_done.set()
                # The delete runs while this transaction is open.
                await asyncio.sleep(SECONDS_BEFORE_FIRST_COMMIT)

    async def delete_node() -> None:
        if not delete_first:
            await first_is_done.wait()
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=branch, id=person.id, raise_on_error=True)
            await node.delete(db=dbt)
            if delete_first:
                first_is_done.set()
                # The owner write runs while this transaction is open.
                await asyncio.sleep(SECONDS_BEFORE_FIRST_COMMIT)

    await asyncio.gather(write_owners(), delete_node())

    records = await db.execute_query(
        query="""
MATCH (n:Node {uuid: $node_id})
MATCH (h)-[r:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SET]->()
WHERE (h = n OR EXISTS { (n)-[:HAS_ATTRIBUTE|HAS_OWNER_SET]->(h) })
AND r.branch = $branch AND r.status = "active" AND r.to IS NULL
RETURN count(r) AS open_edges
""",
        params={"node_id": person.id, "branch": branch.name},
    )
    assert records[0]["open_edges"] == 0
    await verify_graph(db=db, kinds=["TestPerson"])


@pytest.mark.parametrize("on_branch", [False, True], ids=["default-branch", "branch"])
async def test_owner_writes_of_two_attributes_and_node_delete_in_open_transactions_do_not_deadlock(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str], on_branch: bool
) -> None:
    branch = await create_branch(db=db, branch_name="two-writes-and-delete") if on_branch else default_branch
    first_is_written = asyncio.Event()

    async def write_owners() -> None:
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            for field_name in ("height", "name"):
                await _write(
                    db=dbt,
                    branch=branch,
                    node_id=person.id,
                    holder=_holder(default_branch=default_branch, field_name=field_name),
                    owner_ids=group_ids[:1],
                )
                first_is_written.set()
                # The delete starts while this transaction holds the node and has not written the next attribute.
                await asyncio.sleep(SECONDS_BEFORE_FIRST_COMMIT)

    async def delete_node() -> None:
        await first_is_written.wait()
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=branch, id=person.id, raise_on_error=True)
            await node.delete(db=dbt)

    # Both writes run to their end, so a failed one leaves no open transaction for the next test.
    results = await asyncio.gather(write_owners(), delete_node(), return_exceptions=True)

    assert results == [None, None]
    await verify_graph(db=db, kinds=["TestPerson"])
