from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetDisplayLabelQuery
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA


async def run_query(db: InfrahubDatabase, branch: Branch, ids: list[str]) -> NodeListGetDisplayLabelQuery:
    query = await NodeListGetDisplayLabelQuery.init(db=db, branch=branch, ids=ids)
    await query.execute(db=db)
    return query


async def get_stored_display_labels(db: InfrahubDatabase, branch: Branch, ids: list[str]) -> dict[str, str]:
    query = await run_query(db=db, branch=branch, ids=ids)
    return query.get_display_label_map()


async def test_stored_display_labels_follow_the_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_yaris_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    yaris_branch = await NodeManager.get_one(db=db, branch=branch, id=car_yaris_main.get_id())
    yaris_branch.color.value = "purple"
    await yaris_branch.save(db=db)
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.get_id())
    await alfred_branch.delete(db=db)
    ids = [car_yaris_main.get_id(), person_jane_main.get_id(), person_alfred_main.get_id(), "not-a-node"]

    labels_main = await get_stored_display_labels(db=db, branch=default_branch, ids=ids)
    labels_branch = await get_stored_display_labels(db=db, branch=branch, ids=ids)

    assert labels_main == {
        car_yaris_main.get_id(): await car_yaris_main.get_display_label(db=db),
        person_jane_main.get_id(): "Jane",
        person_alfred_main.get_id(): "Alfred",
    }
    assert labels_branch == {
        car_yaris_main.get_id(): await yaris_branch.get_display_label(db=db),
        person_jane_main.get_id(): "Jane",
    }
    assert labels_branch[car_yaris_main.get_id()] != labels_main[car_yaris_main.get_id()]


async def test_node_without_stored_display_label_is_left_out(
    db: InfrahubDatabase, default_branch: Branch, person_jane_main: Node, person_john_main: Node
) -> None:
    # A node created before display labels were stored has no display_label attribute at all
    await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $uuid})-[:HAS_ATTRIBUTE]->(attr:Attribute {name: "display_label"})
        DETACH DELETE attr
        """,
        params={"uuid": person_john_main.get_id()},
    )

    labels = await get_stored_display_labels(
        db=db, branch=default_branch, ids=[person_jane_main.get_id(), person_john_main.get_id()]
    )

    assert labels == {person_jane_main.get_id(): "Jane"}


async def test_one_row_per_node_after_a_kind_migration(
    db: InfrahubDatabase, default_branch: Branch, person_jane_main: Node, person_john_main: Node
) -> None:
    """A kind migration leaves two vertices per uuid and two HAS_ATTRIBUTE edges on the old one.

    Only the vertex active on the queried branch is read, and each attribute is resolved once.
    """
    branch = await create_branch(db=db, branch_name="branch1")
    migration_query = await NodeDuplicateQuery.init(
        db=db,
        branch=branch,
        kind_updates_map={
            "TestPerson": SchemaNodeInfo(name="Being", namespace="Test", labels=["TestBeing"], kind="TestBeing")
        },
    )
    await migration_query.execute(db=db)
    ids = [person_jane_main.get_id(), person_john_main.get_id()]
    expected = {person_jane_main.get_id(): "Jane", person_john_main.get_id(): "John"}

    for query_branch in (default_branch, branch):
        query = await run_query(db=db, branch=query_branch, ids=ids)

        assert query.num_of_results == 2
        assert query.get_display_label_map() == expected


async def test_kind_without_template_is_left_out(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    person_jane_main: Node,
) -> None:
    """A kind without a display_label template stores the NULL sentinel, which is not a label."""
    registry.schema.register_schema(schema=CAR_SCHEMA, branch=default_branch.name)
    manufacturer = await Node.init(db=db, schema=TestKind.MANUFACTURER, branch=default_branch)
    await manufacturer.new(db=db, name="Omnicorp")
    await manufacturer.save(db=db)
    assert await manufacturer.get_display_label(db=db) == f"{TestKind.MANUFACTURER}(ID: {manufacturer.get_id()})"

    labels = await get_stored_display_labels(
        db=db, branch=default_branch, ids=[person_jane_main.get_id(), manufacturer.get_id()]
    )

    assert labels == {person_jane_main.get_id(): "Jane"}
