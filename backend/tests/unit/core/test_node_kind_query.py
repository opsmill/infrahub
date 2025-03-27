from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from infrahub.core.node import Node
from infrahub.core.query.node import NodeGetKindQuery
from infrahub.database import InfrahubDatabase


async def test_node_get_kind_query_no_migrated_nodes(
    db: InfrahubDatabase, person_john_main: Node, person_jane_main: Node
) -> None:
    query = await NodeGetKindQuery.init(db=db, ids=[person_john_main.id, person_jane_main.id])
    await query.execute(db=db)

    assert await query.get_node_kind_map() == {person_jane_main.id: "TestPerson", person_john_main.id: "TestPerson"}


async def test_node_get_kind_query_with_migrated_nodes_on_branch(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_yaris_main: Node,
    default_branch: Branch,
) -> None:
    branch = await create_branch(db=db, branch_name="branch1")

    # run migration on branch
    migration_query = await NodeDuplicateQuery.init(
        db=db,
        branch=branch,
        previous_node=SchemaNodeInfo(name="Person", namespace="Test", labels=["TestPerson"], kind="TestPerson"),
        new_node=SchemaNodeInfo(name="Being", namespace="Test", labels=["TestBeing"], kind="TestBeing"),
    )
    await migration_query.execute(db=db)

    # check results on branch
    query = await NodeGetKindQuery.init(
        db=db, branch=branch, ids=[person_john_main.id, person_jane_main.id, car_accord_main.id, car_yaris_main.id]
    )
    await query.execute(db=db)
    assert await query.get_node_kind_map() == {
        person_jane_main.id: "TestBeing",
        person_john_main.id: "TestBeing",
        car_yaris_main.id: "TestCar",
        car_accord_main.id: "TestCar",
    }

    # check results without branch parameter gets latest from any branch
    query = await NodeGetKindQuery.init(
        db=db, ids=[person_john_main.id, person_jane_main.id, car_accord_main.id, car_yaris_main.id]
    )
    await query.execute(db=db)
    assert await query.get_node_kind_map() == {
        person_jane_main.id: "TestBeing",
        person_john_main.id: "TestBeing",
        car_yaris_main.id: "TestCar",
        car_accord_main.id: "TestCar",
    }

    # check results on default branch
    query = await NodeGetKindQuery.init(
        db=db,
        branch=default_branch,
        ids=[person_john_main.id, person_jane_main.id, car_accord_main.id, car_yaris_main.id],
    )
    await query.execute(db=db)
    assert await query.get_node_kind_map() == {
        person_jane_main.id: "TestPerson",
        person_john_main.id: "TestPerson",
        car_yaris_main.id: "TestCar",
        car_accord_main.id: "TestCar",
    }

    # run migration on default branch
    migration_query = await NodeDuplicateQuery.init(
        db=db,
        branch=default_branch,
        previous_node=SchemaNodeInfo(name="Person", namespace="Test", labels=["TestPerson"], kind="TestPerson"),
        new_node=SchemaNodeInfo(name="Being", namespace="Test", labels=["TestBeing"], kind="TestBeing"),
    )
    await migration_query.execute(db=db)

    # check updated results on default branch
    query = await NodeGetKindQuery.init(
        db=db,
        ids=[person_john_main.id, person_jane_main.id, car_accord_main.id, car_yaris_main.id],
    )
    await query.execute(db=db)
    assert await query.get_node_kind_map() == {
        person_jane_main.id: "TestBeing",
        person_john_main.id: "TestBeing",
        car_yaris_main.id: "TestCar",
        car_accord_main.id: "TestCar",
    }
