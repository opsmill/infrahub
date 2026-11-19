import asyncio
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.query.owner_set_attribute import OwnerSetKeyMigrationQuery
from infrahub.core.node import Node
from infrahub.core.ownership.models import NODE_HOLDER, HolderKey, HolderKind, StoredOwnerState, field_holder
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


async def _write(
    db: InfrahubDatabase,
    branch: Branch,
    node_id: str,
    holder: HolderKey,
    owner_ids: list[str],
    at: Timestamp | None = None,
) -> None:
    await OwnershipRepository(db=db, branch=branch, at=None).write(
        node_id=node_id,
        holder=holder,
        state=StoredOwnerState(owner_ids=tuple(owner_ids)),
        write_branch=branch,
        at=at or Timestamp(),
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


async def test_write_of_a_repeated_owner_creates_one_edge(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    owner_id = group_ids[0]
    await _write(db=db, branch=default_branch, node_id=person.id, holder=NODE_HOLDER, owner_ids=[owner_id, owner_id])

    await _write(db=db, branch=default_branch, node_id=person.id, holder=NODE_HOLDER, owner_ids=group_ids[1:])

    assert await read_owners(db=db, branch=default_branch, node_id=person.id, holder=NODE_HOLDER) == tuple(
        group_ids[1:]
    )


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


@pytest.mark.parametrize(
    ("field_name", "on_branch"),
    [
        pytest.param(field_name, on_branch, id=f"{branch_id}-{field_name or 'node'}")
        for branch_id, on_branch in (("default-branch", False), ("branch", True))
        for field_name in (None, "name")
    ],
)
async def test_owner_write_at_a_time_before_a_committed_node_delete_fails(
    db: InfrahubDatabase,
    default_branch: Branch,
    person: Node,
    group_ids: list[str],
    field_name: str | None,
    on_branch: bool,
) -> None:
    branch = await create_branch(db=db, branch_name="write-before-delete") if on_branch else default_branch
    holder = _holder(default_branch=default_branch, field_name=field_name) if field_name else NODE_HOLDER
    # A write takes its time before it waits for the lock that the delete holds.
    write_at = Timestamp()
    node = await NodeManager.get_one(db=db, branch=branch, id=person.id, raise_on_error=True)
    await node.delete(db=db)

    with pytest.raises(QueryError):
        await _write(db=db, branch=branch, node_id=person.id, holder=holder, owner_ids=group_ids[:1], at=write_at)

    records = await db.execute_query(
        query="""
MATCH (n:Node {uuid: $node_id})
MATCH (h)-[r:HAS_OWNER|HAS_OWNER_SET]->()
WHERE (h = n OR EXISTS { (n)-[:HAS_ATTRIBUTE|HAS_OWNER_SET]->(h) })
AND r.status = "active" AND r.to IS NULL
RETURN count(r) AS open_edges
""",
        params={"node_id": person.id},
    )
    assert records[0]["open_edges"] == 0
    await verify_graph(db=db, kinds=["TestPerson"])


async def test_owner_write_on_a_branch_ignores_a_later_node_delete_on_the_default_branch(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    branch = await create_branch(db=db, branch_name="write-before-main-delete")
    write_at = Timestamp()
    await person.delete(db=db)

    await _write(db=db, branch=branch, node_id=person.id, holder=NODE_HOLDER, owner_ids=group_ids[:1], at=write_at)

    assert await read_owners(db=db, branch=branch, node_id=person.id, holder=NODE_HOLDER) == tuple(group_ids[:1])


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


@pytest.mark.parametrize("on_branch", [False, True], ids=["default-branch", "branch"])
async def test_node_update_and_node_delete_in_open_transactions_do_not_deadlock(
    db: InfrahubDatabase, default_branch: Branch, person: Node, on_branch: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    branch = await create_branch(db=db, branch_name="update-and-delete") if on_branch else default_branch
    attribute_is_written = asyncio.Event()

    async def pause_after_the_attributes(*args: Any, **kwargs: Any) -> None:
        attribute_is_written.set()
        # The delete starts while this transaction holds the attribute and has not written the node.
        await asyncio.sleep(SECONDS_BEFORE_FIRST_COMMIT)

    monkeypatch.setattr(Node, "_recompute_local_jinja2", pause_after_the_attributes)

    async def update_node() -> None:
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=branch, id=person.id, raise_on_error=True)
            node.name.value = "Jane"
            await node.save(db=dbt)

    async def delete_node() -> None:
        await attribute_is_written.wait()
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=branch, id=person.id, raise_on_error=True)
            await node.delete(db=dbt)

    # Both writes run to their end, so a failed one leaves no open transaction for the next test.
    results = await asyncio.gather(update_node(), delete_node(), return_exceptions=True)

    assert results == [None, None]
    await verify_graph(db=db, kinds=["TestPerson"])


async def test_attribute_rename_gives_no_set_to_a_node_whose_delete_commits_while_the_rename_waits(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    profile = await Node.init(db=db, schema="ProfileTestPerson")
    await profile.new(db=db, profile_name="person-profile")
    await profile.save(db=db)
    await _write(
        db=db,
        branch=default_branch,
        node_id=profile.id,
        holder=HolderKey(kind=HolderKind.TARGET_SET, attribute="name"),
        owner_ids=group_ids[:1],
    )
    # The rename takes its time before it waits for the lock that the delete holds.
    rename_at = Timestamp()
    node_is_deleted = asyncio.Event()

    async def delete_node() -> None:
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=default_branch, id=profile.id, raise_on_error=True)
            await node.delete(db=dbt)
            node_is_deleted.set()
            # The rename runs while this transaction is open.
            await asyncio.sleep(SECONDS_BEFORE_FIRST_COMMIT)

    async def rename_attribute() -> None:
        await node_is_deleted.wait()
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            query = await OwnerSetKeyMigrationQuery.init(
                db=dbt,
                branch=default_branch,
                at=rename_at,
                node_kinds=["ProfileTestPerson"],
                set_key={"attribute": "name"},
                new_set_key={"attribute": "full_name"},
            )
            await query.execute(db=dbt)

    await asyncio.gather(delete_node(), rename_attribute())

    records = await db.execute_query(
        query="""
MATCH (n:Node {uuid: $node_id})
MATCH (h)-[r:HAS_OWNER|HAS_NO_OWNER|HAS_TARGET_OWNER_SET]->()
WHERE (h = n OR EXISTS { (n)-[:HAS_TARGET_OWNER_SET]->(h) })
AND r.status = "active" AND r.to IS NULL
RETURN count(r) AS open_edges
""",
        params={"node_id": profile.id},
    )
    assert records[0]["open_edges"] == 0
    await verify_graph(db=db, kinds=["ProfileTestPerson"])
