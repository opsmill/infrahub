from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.uniqueness.model import NodeUniquenessQueryRequestValued
from infrahub.core.validators.uniqueness.query import (
    QueryAttributePathValued,
    QueryRelationshipPathValued,
    UniquenessValidationQuery,
)
from infrahub.database import InfrahubDatabase


async def test_query_uniqueness_no_violations(
    db: InfrahubDatabase,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_yaris_main,
    car_prius_main,
    branch: Branch,
) -> None:
    query = await UniquenessValidationQuery.init(
        db=db,
        branch=branch,
        query_request=NodeUniquenessQueryRequestValued(
            kind="TestCar", unique_valued_paths=[QueryAttributePathValued(attribute_name="name", value="notacar")]
        ),
    )
    query_result = await query.execute(db=db)

    assert not query_result.results


async def test_query_uniqueness_one_attr_violation(
    db: InfrahubDatabase, car_accord_main, car_prius_main, branch: Branch, default_branch: Branch
) -> None:
    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[QueryAttributePathValued(attribute_name="nbr_seats", value=5)],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_tuples = query.get_violation_nodes()
    assert set(violation_tuples) == {(car_accord_main.id, "TestCar"), (car_prius_main.id, "TestCar")}

    query_request.unique_valued_paths.append(QueryAttributePathValued(attribute_name="name", value="prius"))
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_tuples = query.get_violation_nodes()
    assert violation_tuples == [(car_prius_main.id, "TestCar")]

    query_request.unique_valued_paths.append(QueryAttributePathValued(attribute_name="color", value="#000000"))
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_tuples = query.get_violation_nodes()
    assert violation_tuples == []


async def test_query_uniqueness_deleted_node_ignored(
    db: InfrahubDatabase,
    car_accord_main,
    car_prius_main,
    branch: Branch,
) -> None:
    node_to_delete = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    await node_to_delete.delete(db=db)

    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[QueryAttributePathValued(attribute_name="nbr_seats", value=5)],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)

    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == [(car_prius_main.id, "TestCar")]


async def test_query_uniqueness_get_latest_update(
    db: InfrahubDatabase,
    car_accord_main,
    car_prius_main,
    branch: Branch,
) -> None:
    car_to_update = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    car_to_update.nbr_seats.value = 3
    await car_to_update.save(db=db)

    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[QueryAttributePathValued(attribute_name="nbr_seats", value=3)],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == [(car_accord_main.id, "TestCar")]


async def test_query_uniqueness_multiple_attribute_violations(
    db: InfrahubDatabase,
    car_accord_main,
    car_prius_main,
    car_volt_main,
    car_camry_main,
    branch: Branch,
    default_branch: Branch,
) -> None:
    for car_id in (car_volt_main.id, car_camry_main.id, car_accord_main.id):
        car_to_update = await NodeManager.get_one(id=car_id, db=db, branch=branch)
        car_to_update.color.value = "#ffffff"
        await car_to_update.save(db=db)

    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[
            QueryAttributePathValued(attribute_name="nbr_seats", value=5),
            QueryAttributePathValued(attribute_name="color", value="#ffffff"),
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert set(violation_nodes) == {(car_camry_main.id, "TestCar"), (car_accord_main.id, "TestCar")}


async def test_query_relationship_uniqueness_no_violations(
    db: InfrahubDatabase,
    car_accord_main,
    car_prius_main,
    person_jane_main,
    person_john_main,
    person_albert_main,
    branch: Branch,
) -> None:
    car_to_update = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    await car_to_update.owner.update(data=person_jane_main, db=db)
    await car_to_update.save(db=db)

    person_to_update = await NodeManager.get_one(id=person_jane_main.id, db=db, branch=branch)
    person_to_update.height.value = person_john_main.height.value - 1
    await person_to_update.save(db=db)

    car_schema = db.schema.get("TestCar", branch=branch, duplicate=False)
    owner_rel_schema = car_schema.get_relationship(name="owner")

    # relationship peer only
    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[
            QueryRelationshipPathValued(
                relationship_schema=owner_rel_schema,
                peer_id=person_albert_main.id,
                attribute_name=None,
                attribute_value=None,
            )
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == []

    # relationship attribute value only
    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[
            QueryRelationshipPathValued(
                relationship_schema=owner_rel_schema, peer_id=None, attribute_name="height", attribute_value=5000
            )
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == []

    # attr and relationship peer
    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[
            QueryAttributePathValued(attribute_name="name", value=person_to_update.height.value),
            QueryRelationshipPathValued(
                relationship_schema=owner_rel_schema,
                peer_id=person_john_main.id,
                attribute_name=None,
                attribute_value=None,
            ),
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == []

    # attr and relationship value
    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[
            QueryAttributePathValued(attribute_name="name", value=person_to_update.height.value),
            QueryRelationshipPathValued(
                relationship_schema=owner_rel_schema, peer_id=None, attribute_name="height", attribute_value=5000
            ),
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == []


async def test_query_relationship_uniqueness_one_violation(
    db: InfrahubDatabase,
    car_accord_main,
    car_prius_main,
    person_jane_main,
    person_john_main,
    person_albert_main,
    branch: Branch,
) -> None:
    car_accord_branch = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
    await car_accord_branch.owner.update(data=person_jane_main, db=db)
    await car_accord_branch.save(db=db)

    person_jane_branch = await NodeManager.get_one(id=person_jane_main.id, db=db, branch=branch)
    person_jane_branch.height.value = person_john_main.height.value - 1
    await person_jane_branch.save(db=db)

    car_schema = db.schema.get("TestCar", branch=branch, duplicate=False)
    owner_rel_schema = car_schema.get_relationship(name="owner")

    # relationship peer only
    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[
            QueryRelationshipPathValued(
                relationship_schema=owner_rel_schema,
                peer_id=person_jane_main.id,
                attribute_name=None,
                attribute_value=None,
            )
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == [(car_accord_main.id, "TestCar")]

    # relationship attribute value only
    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[
            QueryRelationshipPathValued(
                relationship_schema=owner_rel_schema,
                peer_id=None,
                attribute_name="height",
                attribute_value=person_jane_branch.height.value,
            )
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == [(car_accord_main.id, "TestCar")]

    # attr and relationship peer
    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[
            QueryAttributePathValued(attribute_name="name", value=car_prius_main.name.value),
            QueryRelationshipPathValued(
                relationship_schema=owner_rel_schema,
                peer_id=person_john_main.id,
                attribute_name=None,
                attribute_value=None,
            ),
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == [(car_prius_main.id, "TestCar")]

    # attr and relationship value
    query_request = NodeUniquenessQueryRequestValued(
        kind="TestCar",
        unique_valued_paths=[
            QueryAttributePathValued(attribute_name="name", value=car_accord_main.name.value),
            QueryRelationshipPathValued(
                relationship_schema=owner_rel_schema,
                peer_id=None,
                attribute_name="height",
                attribute_value=person_jane_branch.height.value,
            ),
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == [(car_accord_main.id, "TestCar")]


async def test_query_relationship_no_violation_same_peer_different_rels(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    john = await Node.init(schema="TestPerson", db=db)
    await john.new(db=db, name="John", height=175)
    await john.save(db=db)
    jane = await Node.init(schema="TestPerson", db=db)
    await jane.new(db=db, name="Jane", height=165)
    await jane.save(db=db)
    johns_dog = await Node.init(schema="TestDog", db=db)
    await johns_dog.new(db=db, name="J-dog", breed="mixed", owner=john, best_friend=jane)
    await johns_dog.save(db=db)
    jane_dog = await Node.init(schema="TestDog", db=db)
    await jane_dog.new(db=db, name="Jane-dog", breed="mixed", owner=jane, best_friend=jane)
    await jane_dog.save(db=db)

    branch = await create_branch(db=db, branch_name="branch")
    joe = await Node.init(schema="TestPerson", db=db, branch=branch)
    await joe.new(db=db, name="Joe", height=175)
    await joe.save(db=db)
    joes_dog = await Node.init(schema="TestDog", db=db, branch=branch)
    await joes_dog.new(db=db, name="Joe-dog", breed="mixed", owner=joe, best_friend=jane)
    await joes_dog.save(db=db)

    dog_schema = db.schema.get("TestDog", duplicate=False)
    owner_rel_schema = dog_schema.get_relationship("owner")
    best_friend_rel_schema = dog_schema.get_relationship("best_friend")

    query_request = NodeUniquenessQueryRequestValued(
        kind="TestDog",
        unique_valued_paths=[
            QueryRelationshipPathValued(
                relationship_schema=owner_rel_schema, peer_id=jane.id, attribute_name=None, attribute_value=None
            )
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert violation_nodes == [(jane_dog.id, "TestDog")]

    query_request = NodeUniquenessQueryRequestValued(
        kind="TestDog",
        unique_valued_paths=[
            QueryRelationshipPathValued(
                relationship_schema=best_friend_rel_schema, peer_id=jane.id, attribute_name=None, attribute_value=None
            )
        ],
    )
    query = await UniquenessValidationQuery.init(db=db, branch=branch, query_request=query_request)
    await query.execute(db=db)
    violation_nodes = query.get_violation_nodes()
    assert set(violation_nodes) == {(jane_dog.id, "TestDog"), (joes_dog.id, "TestDog"), (johns_dog.id, "TestDog")}
