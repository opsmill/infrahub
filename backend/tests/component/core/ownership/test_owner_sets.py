import asyncio
from typing import Any

import pytest
from neo4j.exceptions import TransientError

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.query.owner_set_attribute import OwnerSetKeyMigrationQuery
from infrahub.core.node import Node
from infrahub.core.ownership.fields import NODE_OWNERS_FIELD, owner_list_value
from infrahub.core.ownership.models import NODE_HOLDER, HolderKey, HolderKind, StoredOwnerState, field_holder
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.writer import OwnershipWriter
from infrahub.core.query.node import NodeLockQuery
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import GraphCheck, collect_graph_violations, verify_graph
from infrahub.exceptions import QueryError
from tests.helpers.ownership import SECONDS_TO_WAIT, USER_ID, read_owners, wait_for_the_other_write


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
            await wait_for_the_other_write(db=db, other=second)

    async def second_write() -> None:
        await asyncio.wait_for(first_is_written.wait(), timeout=SECONDS_TO_WAIT)
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            await _write(db=dbt, branch=default_branch, node_id=person.id, holder=holder, owner_ids=group_ids[1:])

    second = asyncio.ensure_future(second_write())
    await asyncio.gather(first_write(), second)

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
            await wait_for_the_other_write(db=db, other=second)

    async def second_write() -> None:
        await asyncio.wait_for(first_is_written.wait(), timeout=SECONDS_TO_WAIT)
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            await _write(db=dbt, branch=branch, node_id=person.id, holder=NODE_HOLDER, owner_ids=group_ids[:1])

    second = asyncio.ensure_future(second_write())
    await asyncio.gather(first_write(), second)

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


async def test_writer_records_a_repeated_owner_once_in_the_changelog(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    owner_id = group_ids[0]
    writer = OwnershipWriter(repository=OwnershipRepository(db=db, branch=default_branch, at=None))

    await writer.apply(
        node=person,
        holder=NODE_HOLDER,
        state=StoredOwnerState(owner_ids=(owner_id, owner_id)),
        at=Timestamp(),
        user_id=USER_ID,
    )

    assert person.node_changelog.attributes[NODE_OWNERS_FIELD].value == owner_list_value(owner_ids=(owner_id,))


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


async def test_graph_validation_reports_an_open_owner_edge_of_a_set_of_a_deleted_node(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    holder = _holder(default_branch=default_branch, field_name="cars")
    await _write(db=db, branch=default_branch, node_id=person.id, holder=holder, owner_ids=group_ids[:1])
    await person.delete(db=db)
    await verify_graph(db=db, kinds=["TestPerson"])

    await db.execute_query(
        query="""
MATCH (:Node {uuid: $node_id})-[:HAS_OWNER_SET]->(:OwnerSet)-[r:HAS_OWNER]->(:Node)
SET r.to = NULL
""",
        params={"node_id": person.id},
    )

    violations = await collect_graph_violations(db=db, kinds=["TestPerson"])
    assert [violation.check for violation in violations] == [GraphCheck.ORPHANED_ACTIVE_EDGES]
    assert "HAS_OWNER edge on OwnerSet 'testcar__testperson'" in violations[0].message


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
            await asyncio.wait_for(first_is_done.wait(), timeout=SECONDS_TO_WAIT)
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            if delete_first:
                with pytest.raises(QueryError):
                    await _write(db=dbt, branch=branch, node_id=person.id, holder=holder, owner_ids=group_ids[:1])
            else:
                await _write(db=dbt, branch=branch, node_id=person.id, holder=holder, owner_ids=group_ids[:1])
                first_is_done.set()
                # The delete runs while this transaction is open.
                await wait_for_the_other_write(db=db, other=deletion)

    async def delete_node() -> None:
        if not delete_first:
            await asyncio.wait_for(first_is_done.wait(), timeout=SECONDS_TO_WAIT)
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=branch, id=person.id, raise_on_error=True)
            await node.delete(db=dbt)
            if delete_first:
                first_is_done.set()
                # The owner write runs while this transaction is open.
                await wait_for_the_other_write(db=db, other=owner_write)

    owner_write = asyncio.ensure_future(write_owners())
    deletion = asyncio.ensure_future(delete_node())
    await asyncio.gather(owner_write, deletion)

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
                await wait_for_the_other_write(db=db, other=deletion)

    async def delete_node() -> None:
        await asyncio.wait_for(first_is_written.wait(), timeout=SECONDS_TO_WAIT)
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=branch, id=person.id, raise_on_error=True)
            await node.delete(db=dbt)

    # Both writes run to their end, so a failed one leaves no open transaction for the next test.
    deletion = asyncio.ensure_future(delete_node())
    results = await asyncio.gather(write_owners(), deletion, return_exceptions=True)

    assert results == [None, None]
    await verify_graph(db=db, kinds=["TestPerson"])


@pytest.mark.parametrize("on_branch", [False, True], ids=["default-branch", "branch"])
async def test_updates_of_two_nodes_in_reverse_order_in_open_transactions_deadlock(
    db: InfrahubDatabase, default_branch: Branch, person: Node, on_branch: bool
) -> None:
    other = await Node.init(db=db, schema="TestPerson")
    await other.new(db=db, name="Jane")
    await other.save(db=db)
    branch = await create_branch(db=db, branch_name="reverse-order") if on_branch else default_branch
    first_is_written = asyncio.Event()
    second_is_written = asyncio.Event()

    async def update(
        node_ids: tuple[str, str], name: str, is_written: asyncio.Event, other_is_written: asyncio.Event
    ) -> None:
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            first = await NodeManager.get_one(db=dbt, branch=branch, id=node_ids[0], raise_on_error=True)
            first.name.value = name
            await first.save(db=dbt)
            is_written.set()
            await asyncio.wait_for(other_is_written.wait(), timeout=SECONDS_TO_WAIT)
            second = await NodeManager.get_one(db=dbt, branch=branch, id=node_ids[1], raise_on_error=True)
            second.height.value = 180
            await second.save(db=dbt)

    # Both writes run to their end, so a failed one leaves no open transaction for the next test.
    results = await asyncio.gather(
        update((person.id, other.id), "John Doe", first_is_written, second_is_written),
        update((other.id, person.id), "Jane Doe", second_is_written, first_is_written),
        return_exceptions=True,
    )

    errors = [result for result in results if result is not None]
    assert len(errors) == 1
    assert isinstance(errors[0], TransientError)
    assert errors[0].code == "Neo.TransientError.Transaction.DeadlockDetected"
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
        await wait_for_the_other_write(db=db, other=deletion)

    monkeypatch.setattr(Node, "_recompute_local_jinja2", pause_after_the_attributes)

    async def update_node() -> None:
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=branch, id=person.id, raise_on_error=True)
            node.name.value = "Jane"
            await node.save(db=dbt)

    async def delete_node() -> None:
        await asyncio.wait_for(attribute_is_written.wait(), timeout=SECONDS_TO_WAIT)
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=branch, id=person.id, raise_on_error=True)
            await node.delete(db=dbt)

    # Both writes run to their end, so a failed one leaves no open transaction for the next test.
    deletion = asyncio.ensure_future(delete_node())
    results = await asyncio.gather(update_node(), deletion, return_exceptions=True)

    assert results == [None, None]
    await verify_graph(db=db, kinds=["TestPerson"])


async def test_owner_update_that_waits_for_the_node_lock_replaces_the_owner_written_meanwhile(
    db: InfrahubDatabase, default_branch: Branch, person: Node, group_ids: list[str]
) -> None:
    holder = HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name")
    node_is_locked = asyncio.Event()

    async def write_while_the_update_waits() -> None:
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            lock_query = await NodeLockQuery.init(db=dbt, node=person)
            await lock_query.execute(db=dbt)
            node_is_locked.set()
            await wait_for_the_other_write(db=db, other=update)
            await _write(db=dbt, branch=default_branch, node_id=person.id, holder=holder, owner_ids=group_ids[:1])

    async def update_owner() -> None:
        await asyncio.wait_for(node_is_locked.wait(), timeout=SECONDS_TO_WAIT)
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=default_branch, id=person.id, raise_on_error=True)
            node.name.owner = group_ids[1]
            await node.save(db=dbt)

    update = asyncio.ensure_future(update_owner())
    await asyncio.gather(write_while_the_update_waits(), update)

    assert await read_owners(db=db, branch=default_branch, node_id=person.id, holder=holder) == tuple(group_ids[1:])


async def test_value_update_that_waits_behind_a_node_delete_fails_and_leaves_a_valid_graph(
    db: InfrahubDatabase, default_branch: Branch, person: Node
) -> None:
    node_is_locked = asyncio.Event()

    async def delete_while_the_update_waits() -> None:
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            lock_query = await NodeLockQuery.init(db=dbt, node=person)
            await lock_query.execute(db=dbt)
            node = await NodeManager.get_one(db=dbt, branch=default_branch, id=person.id, raise_on_error=True)
            node_is_locked.set()
            await wait_for_the_other_write(db=db, other=update)
            await node.delete(db=dbt)

    async def update_value() -> None:
        await asyncio.wait_for(node_is_locked.wait(), timeout=SECONDS_TO_WAIT)
        async with db.start_session() as session_db, session_db.start_transaction() as dbt:
            node = await NodeManager.get_one(db=dbt, branch=default_branch, id=person.id, raise_on_error=True)
            node.name.value = "Jane"
            await node.save(db=dbt)

    update = asyncio.ensure_future(update_value())
    results = await asyncio.gather(delete_while_the_update_waits(), update, return_exceptions=True)

    assert results[0] is None
    assert isinstance(results[1], Exception)
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
            await wait_for_the_other_write(db=db, other=rename)

    async def rename_attribute() -> None:
        await asyncio.wait_for(node_is_deleted.wait(), timeout=SECONDS_TO_WAIT)
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

    rename = asyncio.ensure_future(rename_attribute())
    await asyncio.gather(delete_node(), rename)

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
