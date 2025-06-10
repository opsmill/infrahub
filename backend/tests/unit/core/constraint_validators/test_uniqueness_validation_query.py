from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.validators.uniqueness.model import NodeUniquenessQueryRequestValued
from infrahub.core.validators.uniqueness.query import QueryAttributePathValued, UniquenessValidationQuery
from infrahub.database import InfrahubDatabase


async def test_query_uniqueness_no_violations(
    db: InfrahubDatabase,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_yaris_main,
    car_prius_main,
    branch: Branch,
):
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
):
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
):
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


# async def test_query_uniqueness_get_latest_update(
#     db: InfrahubDatabase,
#     car_accord_main,
#     car_prius_main,
#     branch: Branch,
# ):
#     car_to_update = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
#     car_to_update.nbr_seats.value = 3
#     await car_to_update.save(db=db)

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar",
#             unique_attribute_paths=[
#                 {"attribute_name": "name", "property_name": "value"},
#                 {"attribute_name": "nbr_seats", "property_name": "value"},
#             ],
#         ),
#     )
#     query_result = await query.execute(db=db)

#     assert not query_result.results


# async def test_query_uniqueness_cross_branch_conflict(
#     db: InfrahubDatabase,
#     car_accord_main,
#     car_prius_main,
#     person_john_main,
#     default_branch: Branch,
# ):
#     branch_2 = await create_branch(branch_name="branch2", db=db)
#     new_car_main = await Node.init(db=db, schema="TestCar", branch=default_branch)
#     await new_car_main.new(db=db, name="Thunderbolt", nbr_seats=2, is_electric=True, owner=person_john_main)
#     await new_car_main.save(db=db)
#     new_car_branch = await Node.init(db=db, schema="TestCar", branch=branch_2)
#     await new_car_branch.new(db=db, name="Thunderbolt", nbr_seats=4, is_electric=True, owner=person_john_main)
#     await new_car_branch.save(db=db)

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch_2,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar", unique_attribute_paths=[{"attribute_name": "name", "property_name": "value"}]
#         ),
#     )
#     query_result = await query.execute(db=db)

#     assert len(query_result.results) == 2
#     expected_result_dicts = [
#         {
#             "attr_name": "name",
#             "node_id": new_car_main.id,
#             "node_count": 2,
#             "attr_value": "Thunderbolt",
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "name",
#             "node_id": new_car_branch.id,
#             "node_count": 2,
#             "attr_value": "Thunderbolt",
#             "relationship_identifier": None,
#             "deepest_branch_name": "branch2",
#         },
#     ]
#     for result in query_result.results:
#         serial_result = dict(result.data)
#         assert serial_result in expected_result_dicts


# async def test_query_uniqueness_multiple_attribute_violations(
#     db: InfrahubDatabase,
#     car_accord_main,
#     car_prius_main,
#     car_volt_main,
#     car_camry_main,
#     branch: Branch,
#     default_branch: Branch,
# ):
#     for car_id in (car_volt_main.id, car_camry_main.id):
#         car_to_update = await NodeManager.get_one(id=car_id, db=db, branch=branch)
#         car_to_update.color.value = "#ffffff"
#         await car_to_update.save(db=db)

#     expected_result_dicts = [
#         {
#             "attr_name": "nbr_seats",
#             "node_id": node_id,
#             "node_count": 3,
#             "attr_value": 5,
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         }
#         for node_id in (car_accord_main.id, car_prius_main.id, car_camry_main.id)
#     ]
#     expected_result_dicts += [
#         {
#             "attr_name": "color",
#             "node_id": node_id,
#             "node_count": 2,
#             "attr_value": "#ffffff",
#             "relationship_identifier": None,
#             "deepest_branch_name": branch.name,
#         }
#         for node_id in (car_volt_main.id, car_camry_main.id)
#     ]
#     expected_result_dicts += [
#         {
#             "attr_name": "color",
#             "node_id": node_id,
#             "node_count": 2,
#             "attr_value": "#444444",
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         }
#         for node_id in (car_accord_main.id, car_prius_main.id)
#     ]

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar",
#             unique_attribute_paths=[
#                 {"attribute_name": "name", "property_name": "value"},
#                 {"attribute_name": "color", "property_name": "value"},
#                 {"attribute_name": "nbr_seats", "property_name": "value"},
#             ],
#         ),
#     )
#     query_result = await query.execute(db=db)

#     assert len(query_result.results) == 7
#     for result in query_result.results:
#         serial_result = dict(result.data)
#         assert serial_result in expected_result_dicts


# async def test_query_relationship_uniqueness_no_violations(
#     db: InfrahubDatabase,
#     car_accord_main,
#     car_prius_main,
#     person_jane_main,
#     person_john_main,
#     branch: Branch,
# ):
#     car_to_update = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
#     await car_to_update.owner.update(data=person_jane_main, db=db)
#     await car_to_update.save(db=db)

#     person_to_update = await NodeManager.get_one(id=person_jane_main.id, db=db, branch=branch)
#     person_to_update.height.value = person_john_main.height.value - 1
#     await person_to_update.save(db=db)

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar",
#             unique_attribute_paths=[{"attribute_name": "name", "property_name": "value"}],
#             relationship_attribute_paths=[{"identifier": "testcar__testperson", "attribute_name": "height"}],
#         ),
#     )
#     query_result = await query.execute(db=db)

#     assert not query_result.results


# async def test_query_relationship_uniqueness_one_violation(
#     db: InfrahubDatabase,
#     car_accord_main,
#     car_prius_main,
#     person_jane_main,
#     person_john_main,
#     branch: Branch,
#     default_branch: Branch,
# ):
#     car_to_update = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
#     await car_to_update.owner.update(data=person_jane_main, db=db)
#     await car_to_update.save(db=db)
#     person_to_update = await NodeManager.get_one(id=person_jane_main.id, db=db, branch=branch)
#     person_to_update.height.value = person_john_main.height.value
#     await person_to_update.save(db=db)

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar",
#             unique_attribute_paths=[{"attribute_name": "name", "property_name": "value"}],
#             relationship_attribute_paths=[{"identifier": "testcar__testperson", "attribute_name": "height"}],
#         ),
#     )
#     query_result = await query.execute(db=db)

#     assert len(query_result.results) == 2
#     expected_result_dicts = [
#         {
#             "attr_name": "height",
#             "node_id": car_accord_main.id,
#             "node_count": 2,
#             "attr_value": 180,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": branch.name,
#         },
#         {
#             "attr_name": "height",
#             "node_id": car_prius_main.id,
#             "node_count": 2,
#             "attr_value": 180,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#     ]
#     for result in query_result.results:
#         serial_result = dict(result.data)
#         assert serial_result in expected_result_dicts


# async def test_query_relationship_and_attribute_uniqueness_violations(
#     db: InfrahubDatabase,
#     car_accord_main,
#     car_prius_main,
#     person_jane_main,
#     person_john_main,
#     branch: Branch,
#     default_branch: Branch,
# ):
#     car_to_update = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
#     await car_to_update.owner.update(data=person_jane_main, db=db)
#     await car_to_update.save(db=db)
#     person_to_update = await NodeManager.get_one(id=person_jane_main.id, db=db, branch=branch)
#     person_to_update.height.value = person_john_main.height.value
#     await person_to_update.save(db=db)
#     expected_result_dicts = [
#         {
#             "attr_name": "nbr_seats",
#             "node_id": car_accord_main.id,
#             "node_count": 2,
#             "attr_value": 5,
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "nbr_seats",
#             "node_id": car_prius_main.id,
#             "node_count": 2,
#             "attr_value": 5,
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "height",
#             "node_id": car_accord_main.id,
#             "node_count": 2,
#             "attr_value": 180,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": branch.name,
#         },
#         {
#             "attr_name": "height",
#             "node_id": car_prius_main.id,
#             "node_count": 2,
#             "attr_value": 180,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#     ]

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar",
#             unique_attribute_paths=[
#                 {"attribute_name": "name", "property_name": "value"},
#                 {"attribute_name": "nbr_seats", "property_name": "value"},
#             ],
#             relationship_attribute_paths=[{"identifier": "testcar__testperson", "attribute_name": "height"}],
#         ),
#     )
#     query_result = await query.execute(db=db)

#     assert len(query_result.results) == 4
#     for result in query_result.results:
#         serial_result = dict(result.data)
#         assert serial_result in expected_result_dicts


# async def test_query_relationship_violation_no_attribute(
#     db: InfrahubDatabase,
#     car_accord_main,
#     car_prius_main,
#     car_camry_main,
#     person_john_main,
#     branch: Branch,
#     default_branch: Branch,
# ):
#     car_to_update = await NodeManager.get_one(id=car_camry_main.id, db=db, branch=branch)
#     await car_to_update.owner.update(data=person_john_main, db=db)
#     await car_to_update.save(db=db)
#     expected_result_dicts = [
#         {
#             "attr_name": "id",
#             "node_id": car_accord_main.id,
#             "node_count": 3,
#             "attr_value": person_john_main.id,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "id",
#             "node_id": car_prius_main.id,
#             "node_count": 3,
#             "attr_value": person_john_main.id,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "id",
#             "node_id": car_camry_main.id,
#             "node_count": 3,
#             "attr_value": person_john_main.id,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": branch.name,
#         },
#     ]

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar", relationship_attribute_paths=[{"identifier": "testcar__testperson", "attribute_name": None}]
#         ),
#     )
#     query_result = await query.execute(db=db)

#     assert len(query_result.results) == 3
#     for result in query_result.results:
#         serial_result = dict(result.data)
#         assert serial_result in expected_result_dicts


# async def test_query_relationship_no_violation_same_peer_different_rels(
#     db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
# ):
#     john = await Node.init(schema="TestPerson", db=db)
#     await john.new(db=db, name="John", height=175)
#     await john.save(db=db)
#     jane = await Node.init(schema="TestPerson", db=db)
#     await jane.new(db=db, name="Jane", height=165)
#     await jane.save(db=db)
#     johns_dog = await Node.init(schema="TestDog", db=db)
#     await johns_dog.new(db=db, name="J-dog", breed="mixed", owner=john, best_friend=jane)
#     await johns_dog.save(db=db)
#     jane_dog = await Node.init(schema="TestDog", db=db)
#     await jane_dog.new(db=db, name="Jane-dog", breed="mixed", owner=jane, best_friend=jane)
#     await jane_dog.save(db=db)

#     branch = await create_branch(db=db, branch_name="branch")
#     joe = await Node.init(schema="TestPerson", db=db, branch=branch)
#     await joe.new(db=db, name="Joe", height=175)
#     await joe.save(db=db)
#     joes_dog = await Node.init(schema="TestDog", db=db, branch=branch)
#     await joes_dog.new(db=db, name="Joe-dog", breed="mixed", owner=joe, best_friend=jane)
#     await joes_dog.save(db=db)

#     expected_best_friend_result_dicts = [
#         {
#             "attr_name": "id",
#             "node_id": johns_dog.id,
#             "node_count": 3,
#             "attr_value": jane.id,
#             "relationship_identifier": "person__animal_friend",
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "id",
#             "node_id": jane_dog.id,
#             "node_count": 3,
#             "attr_value": jane.id,
#             "relationship_identifier": "person__animal_friend",
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "id",
#             "node_id": joes_dog.id,
#             "node_count": 3,
#             "attr_value": jane.id,
#             "relationship_identifier": "person__animal_friend",
#             "deepest_branch_name": branch.name,
#         },
#     ]

#     owner_query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestDog", relationship_attribute_paths=[{"identifier": "person__animal", "value": jane.id}]
#         ),
#     )
#     owner_query_result = await owner_query.execute(db=db)
#     assert len(owner_query_result.results) == 0

#     best_friend_query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestDog", relationship_attribute_paths=[{"identifier": "person__animal_friend", "value": jane.id}]
#         ),
#     )
#     best_friend_query_result = await best_friend_query.execute(db=db)
#     assert len(best_friend_query_result.results) == 3
#     for result in best_friend_query_result.results:
#         serial_result = dict(result.data)
#         assert serial_result in expected_best_friend_result_dicts


# async def test_query_response_min_count_0_attribute_paths(
#     db: InfrahubDatabase, car_accord_main, car_prius_main, branch: Branch, default_branch: Branch
# ):
#     expected_result_dicts = [
#         {
#             "attr_name": "nbr_seats",
#             "node_id": car_accord_main.id,
#             "node_count": 2,
#             "attr_value": 5,
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "nbr_seats",
#             "node_id": car_prius_main.id,
#             "node_count": 2,
#             "attr_value": 5,
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "name",
#             "node_id": car_accord_main.id,
#             "node_count": 1,
#             "attr_value": car_accord_main.name.value,
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "name",
#             "node_id": car_prius_main.id,
#             "node_count": 1,
#             "attr_value": car_prius_main.name.value,
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         },
#     ]

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar",
#             unique_attribute_paths=[
#                 {"attribute_name": "name", "property_name": "value"},
#                 {"attribute_name": "nbr_seats", "property_name": "value"},
#             ],
#         ),
#         min_count_required=0,
#     )
#     query_result = await query.execute(db=db)

#     assert len(query_result.results) == 4
#     for result in query_result.results:
#         serial_result = dict(result.data)
#         assert serial_result in expected_result_dicts


# async def test_query_response_min_count_0_relationship_paths(
#     db: InfrahubDatabase, car_camry_main, car_prius_main, branch: Branch, default_branch: Branch
# ):
#     expected_result_dicts = [
#         {
#             "attr_name": "name",
#             "node_id": car_camry_main.id,
#             "node_count": 1,
#             "attr_value": "Jane",
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "name",
#             "node_id": car_prius_main.id,
#             "node_count": 1,
#             "attr_value": "John",
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "height",
#             "node_id": car_camry_main.id,
#             "node_count": 2,
#             "attr_value": 180,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "height",
#             "node_id": car_prius_main.id,
#             "node_count": 2,
#             "attr_value": 180,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#     ]

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar",
#             relationship_attribute_paths=[
#                 {"identifier": "testcar__testperson", "attribute_name": "height"},
#                 {"identifier": "testcar__testperson", "attribute_name": "name"},
#             ],
#         ),
#         min_count_required=0,
#     )
#     query_result = await query.execute(db=db)

#     assert len(query_result.results) == 4
#     for result in query_result.results:
#         serial_result = dict(result.data)
#         assert serial_result in expected_result_dicts


# async def test_query_response_min_count_0_attribute_paths_with_value(
#     db: InfrahubDatabase, car_accord_main, car_prius_main, branch: Branch, default_branch: Branch
# ):
#     expected_result_dicts = [
#         {
#             "attr_name": "nbr_seats",
#             "node_id": car_accord_main.id,
#             "node_count": 2,
#             "attr_value": 5,
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "nbr_seats",
#             "node_id": car_prius_main.id,
#             "node_count": 2,
#             "attr_value": 5,
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "name",
#             "node_id": car_accord_main.id,
#             "node_count": 1,
#             "attr_value": car_accord_main.name.value,
#             "relationship_identifier": None,
#             "deepest_branch_name": default_branch.name,
#         },
#     ]

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar",
#             unique_attribute_paths=[
#                 {"attribute_name": "name", "property_name": "value", "value": "accord"},
#                 {"attribute_name": "nbr_seats", "property_name": "value"},
#             ],
#         ),
#         min_count_required=0,
#     )
#     query_result = await query.execute(db=db)

#     assert len(query_result.results) == 3
#     for result in query_result.results:
#         serial_result = dict(result.data)
#         assert serial_result in expected_result_dicts


# async def test_query_response_min_count_0_relationship_paths_with_value(
#     db: InfrahubDatabase, car_camry_main, car_prius_main, branch: Branch, default_branch: Branch
# ):
#     expected_result_dicts = [
#         {
#             "attr_name": "name",
#             "node_id": car_camry_main.id,
#             "node_count": 1,
#             "attr_value": "Jane",
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "height",
#             "node_id": car_camry_main.id,
#             "node_count": 2,
#             "attr_value": 180,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#         {
#             "attr_name": "height",
#             "node_id": car_prius_main.id,
#             "node_count": 2,
#             "attr_value": 180,
#             "relationship_identifier": "testcar__testperson",
#             "deepest_branch_name": default_branch.name,
#         },
#     ]

#     query = await NodeUniqueAttributeConstraintQuery.init(
#         db=db,
#         branch=branch,
#         query_request=NodeUniquenessQueryRequest(
#             kind="TestCar",
#             relationship_attribute_paths=[
#                 {"identifier": "testcar__testperson", "attribute_name": "height"},
#                 {"identifier": "testcar__testperson", "attribute_name": "name", "value": "Jane"},
#             ],
#         ),
#         min_count_required=0,
#     )
#     query_result = await query.execute(db=db)

#     assert len(query_result.results) == 3
#     for result in query_result.results:
#         serial_result = dict(result.data)
#         assert serial_result in expected_result_dicts
