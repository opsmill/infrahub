from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m084_hide_replaced_branch_attribute_owners import Migration084
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.ownership import add_node, create_car

# An owner edge as an earlier release stored it: an owner write on a branch left the edge of the default branch active.
ADD_OWNER_EDGE = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "color"})
MATCH (owner:Node {uuid: $owner_id})
CREATE (a)-[:HAS_OWNER {branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: $to}]->(owner)
"""
# The close of an owner edge, as an earlier release stored a change or a removal of the owner.
CLOSE_OWNER_EDGE = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: "color"})-[r:HAS_OWNER]->(:Node {uuid: $owner_id})
WHERE r.branch = $branch AND r.status = "active" AND r.to IS NULL
SET r.to = $at
"""
ACTIVE_OWNERS = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "color"})
MATCH (a)-[r:HAS_OWNER]->(owner:Node)
WHERE %(branch_filter)s
WITH owner, r
ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
WITH owner, head(collect(r)) AS latest
WHERE latest.status = "active"
RETURN owner.uuid AS owner_id
"""
DELETED_EDGES = """
MATCH (:Attribute)-[r:HAS_OWNER {status: "deleted"}]->(owner:Node)
RETURN owner.uuid AS owner_id, r.branch AS branch, r.from AS from
ORDER BY owner_id, branch, from
"""


async def _add_owner_edge(
    db: InfrahubDatabase, branch: Branch, node_id: str, owner_id: str, to: Timestamp | None = None
) -> None:
    await db.execute_query(
        query=ADD_OWNER_EDGE,
        params={
            "node_id": node_id,
            "owner_id": owner_id,
            "branch": branch.name,
            "branch_level": branch.hierarchy_level,
            "at": Timestamp().to_string(),
            "to": to.to_string() if to else None,
        },
    )


async def _active_owner_ids(
    db: InfrahubDatabase, branch: Branch, node_id: str, at: Timestamp | None = None
) -> set[str]:
    branch_filter, params = branch.get_query_filter_path(at=at)
    records = await db.execute_query(
        query=ACTIVE_OWNERS % {"branch_filter": branch_filter}, params={**params, "node_id": node_id}
    )
    return {record["owner_id"] for record in records}


async def _deleted_edges(db: InfrahubDatabase) -> list[dict]:
    return [dict(record) for record in await db.execute_query(query=DELETED_EDGES)]


async def test_default_branch_owner_closed_after_the_branch_start_is_hidden_on_the_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    """The branch is not rebased, so it still reads the owner edge that the default branch closed."""
    main_owner = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="main-owner")
    branch_owner = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="branch-owner")
    person = await add_node(db=db, kind="TestPerson", name="John")
    car = await create_car(db=db, name="volt", person=person, owner_id=main_owner.id)
    branch = await create_branch(db=db, branch_name="branch1")
    await _add_owner_edge(db=db, branch=branch, node_id=car.id, owner_id=branch_owner.id)
    await db.execute_query(
        query=CLOSE_OWNER_EDGE,
        params={
            "node_id": car.id,
            "owner_id": main_owner.id,
            "branch": default_branch.name,
            "at": Timestamp().to_string(),
        },
    )
    assert await _active_owner_ids(db=db, branch=branch, node_id=car.id) == {main_owner.id, branch_owner.id}

    result = await Migration084().execute(migration_input=MigrationInput(db=db))
    deleted_edges = await _deleted_edges(db=db)
    second_result = await Migration084().execute(migration_input=MigrationInput(db=db))

    assert result.errors == []
    assert second_result.errors == []
    assert [(edge["owner_id"], edge["branch"]) for edge in deleted_edges] == [(main_owner.id, branch.name)]
    assert await _deleted_edges(db=db) == deleted_edges
    assert await _active_owner_ids(db=db, branch=branch, node_id=car.id) == {branch_owner.id}
    assert await _active_owner_ids(db=db, branch=default_branch, node_id=car.id) == set()


async def test_default_branch_owner_closed_before_the_branch_start_gets_no_deleted_edge(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    main_owner = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="main-owner")
    branch_owner = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="branch-owner")
    person = await add_node(db=db, kind="TestPerson", name="John")
    car = await create_car(db=db, name="volt", person=person)
    await _add_owner_edge(db=db, branch=default_branch, node_id=car.id, owner_id=main_owner.id, to=Timestamp())
    branch = await create_branch(db=db, branch_name="branch1")
    await _add_owner_edge(db=db, branch=branch, node_id=car.id, owner_id=branch_owner.id)

    result = await Migration084().execute(migration_input=MigrationInput(db=db))

    assert result.errors == []
    assert await _deleted_edges(db=db) == []
    assert await _active_owner_ids(db=db, branch=branch, node_id=car.id) == {branch_owner.id}


async def test_owner_that_the_branch_wrote_first_and_then_replaced_is_hidden(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    main_owner = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="main-owner")
    branch_owner = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="branch-owner")
    person = await add_node(db=db, kind="TestPerson", name="John")
    car = await create_car(db=db, name="volt", person=person, owner_id=main_owner.id)
    branch = await create_branch(db=db, branch_name="branch1")
    await _add_owner_edge(db=db, branch=branch, node_id=car.id, owner_id=main_owner.id, to=Timestamp())
    await _add_owner_edge(db=db, branch=branch, node_id=car.id, owner_id=branch_owner.id)

    result = await Migration084().execute(migration_input=MigrationInput(db=db))

    assert result.errors == []
    assert await _active_owner_ids(db=db, branch=branch, node_id=car.id) == {branch_owner.id}


async def test_repository_that_the_branch_replaced_gets_no_deleted_edge(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    repository = await add_node(
        db=db, kind=InfrahubKind.REPOSITORY, name="repo01", location="git@github.com:user/repo01.git"
    )
    branch_owner = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="branch-owner")
    person = await add_node(db=db, kind="TestPerson", name="John")
    car = await create_car(db=db, name="volt", person=person)
    await _add_owner_edge(db=db, branch=default_branch, node_id=car.id, owner_id=repository.id)
    branch = await create_branch(db=db, branch_name="branch1")
    await _add_owner_edge(db=db, branch=branch, node_id=car.id, owner_id=branch_owner.id)

    result = await Migration084().execute(migration_input=MigrationInput(db=db))

    assert result.errors == []
    assert await _deleted_edges(db=db) == []


async def test_default_branch_owner_is_hidden_from_the_first_of_two_branch_owner_writes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    main_owner = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="main-owner")
    first_owner = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="first-branch-owner")
    second_owner = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="second-branch-owner")
    person = await add_node(db=db, kind="TestPerson", name="John")
    car = await create_car(db=db, name="volt", person=person, owner_id=main_owner.id)
    branch = await create_branch(db=db, branch_name="branch1")
    before_first_write = Timestamp()
    await _add_owner_edge(db=db, branch=branch, node_id=car.id, owner_id=first_owner.id)
    between_writes = Timestamp()
    # The second owner write of an earlier release closed the edge of the first write.
    await db.execute_query(
        query=CLOSE_OWNER_EDGE,
        params={"node_id": car.id, "owner_id": first_owner.id, "branch": branch.name, "at": Timestamp().to_string()},
    )
    await _add_owner_edge(db=db, branch=branch, node_id=car.id, owner_id=second_owner.id)
    assert await _active_owner_ids(db=db, branch=branch, node_id=car.id, at=between_writes) == {
        main_owner.id,
        first_owner.id,
    }

    result = await Migration084().execute(migration_input=MigrationInput(db=db))
    deleted_edges = await _deleted_edges(db=db)
    second_result = await Migration084().execute(migration_input=MigrationInput(db=db))

    assert result.errors == []
    assert second_result.errors == []
    assert [(edge["owner_id"], edge["branch"]) for edge in deleted_edges] == [(main_owner.id, branch.name)]
    assert await _deleted_edges(db=db) == deleted_edges
    assert await _active_owner_ids(db=db, branch=branch, node_id=car.id, at=before_first_write) == {main_owner.id}
    assert await _active_owner_ids(db=db, branch=branch, node_id=car.id, at=between_writes) == {first_owner.id}
    assert await _active_owner_ids(db=db, branch=branch, node_id=car.id) == {second_owner.id}
    assert await _active_owner_ids(db=db, branch=default_branch, node_id=car.id) == {main_owner.id}
    branch_car = await NodeManager.get_one(
        db=db, id=car.id, branch=branch, include_metadata=MetadataOptions.OWNER, raise_on_error=True
    )
    assert branch_car.color.owner_id == second_owner.id
