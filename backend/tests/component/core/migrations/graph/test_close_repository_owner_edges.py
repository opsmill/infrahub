import pytest
from rich.console import Console

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m084_hide_replaced_branch_attribute_owners import Migration084
from infrahub.core.migrations.graph.m085_close_repository_owner_edges import (
    HideGlobalRepositoryOwnersQuery,
    Migration085,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.ownership.models import HolderKey, HolderKind
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.ownership import ADD_ATTRIBUTE_OWNER, ADD_LINK_OWNER, ADD_NAME_OWNER, add_owner_edge, create_car

CLOSE_NAME_OWNER = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[r:HAS_OWNER]->(:Node {uuid: $owner_id})
WHERE r.branch = $branch AND r.status = "active" AND r.to IS NULL
SET r.to = $at
"""
CLOSE_ATTRIBUTE_OWNER = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: "color"})-[r:HAS_OWNER]->(:Node {uuid: $owner_id})
WHERE r.branch = $branch AND r.status = "active" AND r.to IS NULL
SET r.to = $at
"""
OWNER_EDGES = """
MATCH (holder)-[r:HAS_OWNER]->(owner:Node)
RETURN labels(holder) AS holder_labels, owner.uuid AS owner_id, r.branch AS branch, r.status AS status,
    r.from AS from, r.to AS to
ORDER BY owner_id, branch, from
"""


async def _color_owner_id(
    db: InfrahubDatabase, branch: Branch, node_id: str, at: Timestamp | None = None
) -> str | None:
    car = await NodeManager.get_one(
        db=db, branch=branch, id=node_id, at=at, include_metadata=MetadataOptions.OWNER, raise_on_error=True
    )
    return car.color.owner_id


async def _color_owner_ids(
    db: InfrahubDatabase, branch: Branch, node_id: str, at: Timestamp | None = None
) -> set[str] | None:
    """Return every owner that the color of the car stores, as the branch reads them, and None without owner state."""
    stored = await OwnershipRepository(db=db, branch=branch, at=at).read(node_ids=[node_id], attributes=True)
    owner_ids = stored[node_id].get(HolderKey(kind=HolderKind.ATTRIBUTE, attribute="color")).owner_ids
    return None if owner_ids is None else set(owner_ids)


async def _owner_edges(db: InfrahubDatabase) -> list[dict]:
    return [dict(record) for record in await db.execute_query(query=OWNER_EDGES)]


async def test_repository_owners_are_closed_and_readable_before_the_upgrade(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await repository.save(db=db)
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="network-team")
    await group.save(db=db)
    person = await Node.init(db=db, schema="TestPerson")
    await person.new(db=db, name="John")
    await person.save(db=db)

    repository_car = await create_car(db=db, name="repository-car", person=person)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=repository_car.id, owner_id=repository.id
    )
    await add_owner_edge(
        db=db, query=ADD_LINK_OWNER, branch=default_branch, node_id=repository_car.id, owner_id=repository.id
    )
    group_car = await create_car(db=db, name="group-car", person=person, owner_id=group.id)
    plain_car = await create_car(db=db, name="plain-car", person=person)
    branch_car = await create_car(db=db, name="branch-car", person=person)
    branch = await create_branch(db=db, branch_name="branch1")
    await add_owner_edge(db=db, query=ADD_ATTRIBUTE_OWNER, branch=branch, node_id=branch_car.id, owner_id=repository.id)
    before_upgrade = Timestamp()
    edges_before = await _owner_edges(db=db)
    assert await _color_owner_id(db=db, branch=default_branch, node_id=repository_car.id) == repository.id
    assert await _color_owner_id(db=db, branch=branch, node_id=branch_car.id) == repository.id

    console = Console(width=1000, log_time=False, log_path=False)
    with console.capture() as capture:
        result = await Migration085().execute(migration_input=MigrationInput(db=db, console=console))
    edges_after = await _owner_edges(db=db)
    with console.capture() as second_capture:
        second_result = await Migration085().execute(migration_input=MigrationInput(db=db, console=console))

    assert result.errors == []
    assert second_result.errors == []
    assert await _owner_edges(db=db) == edges_after
    assert [line.rstrip() for line in capture.get().splitlines()] == [
        "Attributes that a repository owns, before the close: 2",
        f"  TestCar.color, repository {repository.id} (CoreRepository), branch branch1: 1",
        f"  TestCar.color, repository {repository.id} (CoreRepository), branch main: 1",
        "Closed 2 owner edge(s) from attributes to repositories.",
        f"  repository {repository.id} (CoreRepository): 2",
    ]
    assert [line.rstrip() for line in second_capture.get().splitlines()] == [
        "Attributes that a repository owns, before the close: 0",
        "Closed 0 owner edge(s) from attributes to repositories.",
    ]

    assert await _color_owner_id(db=db, branch=default_branch, node_id=repository_car.id) is None
    assert await _color_owner_id(db=db, branch=branch, node_id=branch_car.id) is None
    assert (
        await _color_owner_id(db=db, branch=default_branch, node_id=repository_car.id, at=before_upgrade)
        == repository.id
    )
    assert await _color_owner_id(db=db, branch=branch, node_id=branch_car.id, at=before_upgrade) == repository.id
    assert await _color_owner_id(db=db, branch=default_branch, node_id=group_car.id) == group.id
    assert await _color_owner_id(db=db, branch=default_branch, node_id=plain_car.id) is None

    # No edge is deleted: the two attribute edges to the repository get a `to` time, and the branch gets one
    # `deleted` edge for the edge of the default branch that it reads.
    active = [edge for edge in edges_after if edge["status"] == "active"]
    closed = [edge for edge in active if edge["owner_id"] == repository.id and "Attribute" in edge["holder_labels"]]
    assert len(closed) == 2
    assert all(edge["to"] is not None for edge in closed)
    assert [{**edge, "to": None} for edge in active] == edges_before
    hidden = [edge for edge in edges_after if edge["status"] == "deleted"]
    assert [(edge["holder_labels"], edge["owner_id"], edge["branch"]) for edge in hidden] == [
        (["Attribute"], repository.id, branch.name)
    ]
    link_edges = [edge for edge in edges_after if "Relationship" in edge["holder_labels"]]
    assert [(edge["owner_id"], edge["status"], edge["to"]) for edge in link_edges] == [(repository.id, "active", None)]


async def test_branch_made_before_the_upgrade_reads_no_repository_owner_after_the_upgrade(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await repository.save(db=db)
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="network-team")
    await group.save(db=db)
    person = await Node.init(db=db, schema="TestPerson")
    await person.new(db=db, name="John")
    await person.save(db=db)
    cars: dict[str, str] = {}
    for name in ("inherited", "replaced-on-branch", "closed-on-default-branch"):
        cars[name] = (await create_car(db=db, name=name, person=person)).id
        await add_owner_edge(
            db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=cars[name], owner_id=repository.id
        )
    # The branch does not read an edge that closed before its start or that started after it.
    closed_before_branch = await create_car(db=db, name="closed-before-the-branch", person=person)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=closed_before_branch.id, owner_id=repository.id
    )
    await db.execute_query(
        query=CLOSE_ATTRIBUTE_OWNER,
        params={
            "node_id": closed_before_branch.id,
            "owner_id": repository.id,
            "branch": default_branch.name,
            "at": Timestamp().to_string(),
        },
    )
    branch = await create_branch(db=db, branch_name="branch1")
    added_after_branch = await create_car(db=db, name="added-after-the-branch", person=person)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=added_after_branch.id, owner_id=repository.id
    )
    # An owner write of an earlier release on a branch left the owner edge of the default branch open.
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=branch, node_id=cars["replaced-on-branch"], owner_id=group.id
    )
    await db.execute_query(
        query=CLOSE_ATTRIBUTE_OWNER,
        params={
            "node_id": cars["closed-on-default-branch"],
            "owner_id": repository.id,
            "branch": default_branch.name,
            "at": Timestamp().to_string(),
        },
    )
    before_upgrade = Timestamp()
    owners_before = {
        name: await _color_owner_ids(db=db, branch=branch, node_id=car_id) for name, car_id in cars.items()
    }
    assert owners_before == {
        "inherited": {repository.id},
        "replaced-on-branch": {group.id, repository.id},
        "closed-on-default-branch": {repository.id},
    }

    result = await Migration085().execute(migration_input=MigrationInput(db=db))
    edges_after = await _owner_edges(db=db)
    second_result = await Migration085().execute(migration_input=MigrationInput(db=db))

    assert result.errors == []
    assert second_result.errors == []
    assert await _owner_edges(db=db) == edges_after
    assert {name: await _color_owner_ids(db=db, branch=branch, node_id=car_id) for name, car_id in cars.items()} == {
        "inherited": None,
        "replaced-on-branch": {group.id},
        "closed-on-default-branch": None,
    }
    assert await _color_owner_id(db=db, branch=branch, node_id=cars["inherited"]) is None
    assert {
        name: await _color_owner_ids(db=db, branch=default_branch, node_id=car_id) for name, car_id in cars.items()
    } == dict.fromkeys(cars)
    assert {
        name: await _color_owner_ids(db=db, branch=branch, node_id=car_id, at=before_upgrade)
        for name, car_id in cars.items()
    } == owners_before
    hidden = [(edge["owner_id"], edge["branch"]) for edge in edges_after if edge["status"] == "deleted"]
    assert hidden == [(repository.id, branch.name)] * 3
    assert len([edge for edge in edges_after if edge["status"] == "active"]) == 6


async def test_branch_that_replaced_an_account_owner_with_a_repository_reads_no_owner_after_the_upgrade(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await repository.save(db=db)
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="network-admin", password="unused-password")
    await account.save(db=db)
    person = await Node.init(db=db, schema="TestPerson")
    await person.new(db=db, name="John")
    await person.save(db=db)
    car = await create_car(db=db, name="replaced-by-repository", person=person, owner_id=account.id)
    branch = await create_branch(db=db, branch_name="branch1")
    # An owner write of an earlier release on a branch left the owner edge of the default branch open.
    await add_owner_edge(db=db, query=ADD_ATTRIBUTE_OWNER, branch=branch, node_id=car.id, owner_id=repository.id)
    before_upgrade = Timestamp()
    assert await _color_owner_ids(db=db, branch=branch, node_id=car.id) == {account.id, repository.id}

    # The upgrade runs the migrations in their order.
    for migration in (Migration084(), Migration085()):
        result = await migration.execute(migration_input=MigrationInput(db=db))
        assert result.errors == []

    assert await _color_owner_ids(db=db, branch=branch, node_id=car.id) is None
    assert await _color_owner_ids(db=db, branch=branch, node_id=car.id, at=before_upgrade) == {repository.id}
    assert await _color_owner_ids(db=db, branch=default_branch, node_id=car.id) == {account.id}


async def _name_owner_ids(
    db: InfrahubDatabase, branch: Branch, node_id: str, at: Timestamp | None = None
) -> set[str] | None:
    stored = await OwnershipRepository(db=db, branch=branch, at=at).read(node_ids=[node_id], attributes=True)
    owner_ids = stored[node_id].get(HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name")).owner_ids
    return None if owner_ids is None else set(owner_ids)


async def test_branch_made_before_the_upgrade_reads_no_global_repository_owner_after_the_upgrade(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    global_branch = registry.get_global_branch()
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await repository.save(db=db)
    groups: dict[str, str] = {}
    for name in (
        "owner-group",
        "open-at-upgrade",
        "replaced-before-upgrade",
        "closed-before-the-branch",
        "added-after-the-branch",
    ):
        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name=name)
        await group.save(db=db)
        groups[name] = group.id
    for name in ("open-at-upgrade", "replaced-before-upgrade"):
        await add_owner_edge(
            db=db, query=ADD_NAME_OWNER, branch=global_branch, node_id=groups[name], owner_id=repository.id
        )
    # The branch does not read an edge that closed before its start or that started after it.
    await add_owner_edge(
        db=db,
        query=ADD_NAME_OWNER,
        branch=global_branch,
        node_id=groups["closed-before-the-branch"],
        owner_id=repository.id,
    )
    await db.execute_query(
        query=CLOSE_NAME_OWNER,
        params={
            "node_id": groups["closed-before-the-branch"],
            "owner_id": repository.id,
            "branch": global_branch.name,
            "at": Timestamp().to_string(),
        },
    )
    branch = await create_branch(db=db, branch_name="branch1")
    await add_owner_edge(
        db=db,
        query=ADD_NAME_OWNER,
        branch=global_branch,
        node_id=groups["added-after-the-branch"],
        owner_id=repository.id,
    )
    # An owner write of an earlier release on the global branch closed the old edge only.
    replaced_at = Timestamp().to_string()
    await db.execute_query(
        query=CLOSE_NAME_OWNER,
        params={
            "node_id": groups["replaced-before-upgrade"],
            "owner_id": repository.id,
            "branch": global_branch.name,
            "at": replaced_at,
        },
    )
    await add_owner_edge(
        db=db,
        query=ADD_NAME_OWNER,
        branch=global_branch,
        node_id=groups["replaced-before-upgrade"],
        owner_id=groups["owner-group"],
    )
    before_upgrade = Timestamp()
    holders = ("open-at-upgrade", "replaced-before-upgrade")
    owners_before = {name: await _name_owner_ids(db=db, branch=branch, node_id=groups[name]) for name in holders}
    assert owners_before == {
        "open-at-upgrade": {repository.id},
        "replaced-before-upgrade": {groups["owner-group"], repository.id},
    }

    result = await Migration085().execute(migration_input=MigrationInput(db=db))
    edges_after = await _owner_edges(db=db)
    second_result = await Migration085().execute(migration_input=MigrationInput(db=db))

    assert result.errors == []
    assert second_result.errors == []
    assert await _owner_edges(db=db) == edges_after
    expected = {"open-at-upgrade": None, "replaced-before-upgrade": {groups["owner-group"]}}
    for read_branch in (branch, default_branch):
        assert {
            name: await _name_owner_ids(db=db, branch=read_branch, node_id=groups[name]) for name in holders
        } == expected
    assert {
        name: await _name_owner_ids(db=db, branch=branch, node_id=groups[name], at=before_upgrade) for name in holders
    } == owners_before
    hidden = [(edge["owner_id"], edge["branch"]) for edge in edges_after if edge["status"] == "deleted"]
    assert hidden == [(repository.id, global_branch.name)] * 2


async def test_repository_owners_and_closed_edges_are_printed_when_a_later_query_fails(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await repository.save(db=db)
    person = await Node.init(db=db, schema="TestPerson")
    await person.new(db=db, name="John")
    await person.save(db=db)
    car = await create_car(db=db, name="repository-car", person=person)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=car.id, owner_id=repository.id
    )

    async def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("hide query failed")

    monkeypatch.setattr(HideGlobalRepositoryOwnersQuery, "execute", fail)
    console = Console(width=1000, log_time=False, log_path=False)
    with console.capture() as capture:
        result = await Migration085().execute(migration_input=MigrationInput(db=db, console=console))

    assert result.errors == ["hide query failed"]
    # The close commits before the failure, so the list of owners and the counts of the closed edges must be printed.
    assert [line.rstrip() for line in capture.get().splitlines()] == [
        "Attributes that a repository owns, before the close: 1",
        f"  TestCar.color, repository {repository.id} (CoreRepository), branch main: 1",
        "Closed 1 owner edge(s) from attributes to repositories.",
        f"  repository {repository.id} (CoreRepository): 1",
    ]


async def test_merged_branch_gets_no_deleted_edge(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await repository.save(db=db)
    person = await Node.init(db=db, schema="TestPerson")
    await person.new(db=db, name="John")
    await person.save(db=db)
    car = await create_car(db=db, name="repository-car", person=person)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=car.id, owner_id=repository.id
    )
    branch = await create_branch(db=db, branch_name="branch1")
    branch.status = BranchStatus.MERGED
    await branch.save(db=db)

    result = await Migration085().execute(migration_input=MigrationInput(db=db))

    assert result.errors == []
    assert [edge for edge in await _owner_edges(db=db) if edge["status"] == "deleted"] == []
