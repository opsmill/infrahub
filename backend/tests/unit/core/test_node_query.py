import time
from typing import Dict

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, RelationshipCardinality, RelationshipHierarchyDirection
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.migrations.schema.node_kind_update import (
    NodeKindUpdateMigration,
    NodeKindUpdateMigrationQuery01,
)
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath, SchemaPathType
from infrahub.core.query.node import (
    NodeCreateAllQuery,
    NodeDeleteQuery,
    NodeGetHierarchyQuery,
    NodeGetListQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
    NodeListGetRelationshipsQuery,
)
from infrahub.core.registry import registry
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.database import InfrahubDatabase


async def test_query_NodeCreateAllQuery(db: InfrahubDatabase, default_branch: Branch, car_person_schema, first_account):
    obj = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await obj.new(db=db, name="John", height=180)

    original_start_time = time.time_ns()
    await obj.save(db=db)
    time.time_ns() - original_start_time

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(
        db=db,
        _owner=first_account,
        name="camry",
        nbr_seats=5,
        is_electric=False,
        owner={"id": obj.id, "_relation__source": first_account},
    )

    new_start_time = time.time_ns()
    query = await NodeCreateAllQuery.init(db=db, node=car)
    await query.execute(db=db)
    time.time_ns() - new_start_time

    assert query.get_self_ids()


async def test_query_NodeGetListQuery(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    ids = [person_john_main.id, person_jim_main.id, person_albert_main.id, person_alfred_main.id]
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=person_schema)
    await query.execute(db=db)
    assert sorted(query.get_node_ids()) == sorted(ids)


async def test_query_NodeGetListQuery_filter_id(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=person_schema, filters={"id": person_john_main.id})
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 1


async def test_query_NodeGetListQuery_filter_ids(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    person_schema.order_by = ["height__value"]
    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=person_schema,
        filters={"ids": [person_jim_main.id, person_john_main.id, person_albert_main.id]},
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [person_albert_main.id, person_jim_main.id, person_john_main.id]


async def test_query_NodeGetListQuery_filter_height(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=schema, filters={"height__value": 160})
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_owner(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node, first_account: Node, branch: Branch
):
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name={"value": "Diane", "owner": first_account.id}, height=165)
    await person.save(db=db)

    schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=schema, filters={"any__owner__id": first_account.id}
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 1

    schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=schema, filters={"name__owner__id": first_account.id}
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 1

    schema = registry.schema.get(name="TestPerson", branch=branch)
    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=schema, filters={"height__owner__id": first_account.id}
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 0


async def test_query_NodeGetListQuery_filter_boolean(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=schema, filters={"is_electric__value": False})
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 3


async def test_query_NodeGetListQuery_deleted_node(
    db: InfrahubDatabase, car_accord_main, car_camry_main: Node, car_volt_main, car_yaris_main, branch: Branch
):
    node_to_delete = await NodeManager.get_one(id=car_camry_main.id, db=db, branch=branch)
    await node_to_delete.delete(db=db)

    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.order_by = ["owner__name__value"]

    query = await NodeGetListQuery.init(db=db, branch=branch, schema=schema, filters={"is_electric__value": False})
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_relationship(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    query = await NodeGetListQuery.init(db=db, branch=branch, schema=schema, filters={"owner__name__value": "John"})
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_relationship_ids(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_yaris_main,
    branch: Branch,
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    query = await NodeGetListQuery.init(
        db=db, branch=branch, schema=schema, filters={"owner__ids": [person_john_main.id]}
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_filter_and_sort(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.order_by = ["owner__name__value", "is_electric__value"]

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
        filters={"owner__name__value": "John", "is_electric__value": False},
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 1


async def test_query_NodeGetListQuery_filter_and_sort_with_revision(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    node = await NodeManager.get_one(id=car_volt_main.id, db=db, branch=branch)
    node.is_electric.value = False
    await node.save(db=db)

    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.order_by = ["owner__name__value", "is_electric__value"]

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
        filters={"owner__name__value": "John", "is_electric__value": False},
    )
    await query.execute(db=db)
    assert len(query.get_node_ids()) == 2


async def test_query_NodeGetListQuery_with_generics(db: InfrahubDatabase, group_group1_main, branch: Branch):
    schema = registry.schema.get(name=InfrahubKind.GENERICGROUP, branch=branch)
    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [group_group1_main.id]


async def test_query_NodeGetListQuery_order_by(
    db: InfrahubDatabase, car_accord_main, car_camry_main, car_volt_main, car_yaris_main, branch: Branch
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.order_by = ["owner__name__value", "name__value"]

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
    )
    await query.execute(db=db)
    assert query.get_node_ids() == [car_camry_main.id, car_yaris_main.id, car_accord_main.id, car_volt_main.id]


async def test_query_NodeGetListQuery_order_by_optional_relationship_nulls(
    db: InfrahubDatabase, branch: Branch, car_camry_main, car_accord_main
):
    schema = registry.schema.get(name="TestCar", branch=branch)
    schema.relationships.append(
        RelationshipSchema(
            name="other_car",
            peer="TestCar",
            cardinality=RelationshipCardinality.ONE,
            identifier="testcar__other_car",
        )
    )
    schema.order_by = ["other_car__name__value"]

    query = await NodeGetListQuery.init(
        db=db,
        branch=branch,
        schema=schema,
    )
    await query.execute(db=db)

    assert set(query.get_node_ids()) == {car_accord_main.id, car_camry_main.id}


async def test_query_NodeListGetInfoQuery(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    ids = [person_john_main.id, person_jim_main.id, person_albert_main.id]
    query = await NodeListGetInfoQuery.init(db=db, branch=branch, ids=ids)
    await query.execute(db=db)
    assert len(list(query.get_results_group_by(("n", "uuid")))) == 3


async def test_query_NodeListGetInfoQuery_renamed(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
):
    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    person_schema = candidate_schema.get(name="TestPerson")
    candidate_schema.delete(name="TestPerson")
    person_schema.name = "NewPerson"
    person_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewPerson", schema=person_schema)
    assert person_schema.kind == "Test2NewPerson"

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestPerson"),
        new_node_schema=person_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewPerson", field_name="namespace"
        ),
    )
    query = await NodeKindUpdateMigrationQuery01.init(db=db, branch=branch, migration=migration)
    await query.execute(db=db)

    ids = [person_john_main.id, person_jim_main.id, person_albert_main.id]
    query = await NodeListGetInfoQuery.init(db=db, branch=branch, ids=ids)
    await query.execute(db=db)
    results = [node.labels async for node in query.get_nodes()]
    for result in results:
        assert sorted(result) == ["CoreNode", "Node", "Test2NewPerson"]


async def test_query_NodeListGetAttributeQuery_all_fields(db: InfrahubDatabase, base_dataset_02):
    default_branch = await registry.get_branch(db=db, branch="main")
    branch1 = await registry.get_branch(db=db, branch="branch1")

    # Query all the nodes in main but only c1 and c2 present
    # Expect 4 attributes per node(x2) = 8 attributes
    query = await NodeListGetAttributeQuery.init(db=db, ids=["c1", "c2", "c3"], branch=default_branch)
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2"]
    assert len(list(query.get_results())) == 8
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 4
    assert len(query.get_attributes_group_by_node()["c2"].attrs) == 4

    # Query all the nodes in branch1, c1, c2 and c3 present
    # Expect 15 attributes because each node has 4 but c1at2 has a value both in Main and Branch1
    query = await NodeListGetAttributeQuery.init(db=db, ids=["c1", "c2", "c3"], branch=branch1)
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2", "c3"]
    assert len(list(query.get_results())) == 15
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 4
    assert len(query.get_attributes_group_by_node()["c2"].attrs) == 4
    assert len(query.get_attributes_group_by_node()["c3"].attrs) == 4

    # Query all the nodes in branch1 in isolated mode, only c1 and c3 present
    # Expect 9 attributes because each node has 4 but c1at2 has a value both in Main and Branch1
    branch1.is_isolated = True
    query = await NodeListGetAttributeQuery.init(db=db, ids=["c1", "c2", "c3"], branch=branch1)
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c3"]
    assert len(list(query.get_results())) == 11
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 4
    assert len(query.get_attributes_group_by_node()["c3"].attrs) == 4


async def test_query_NodeListGetAttributeQuery_with_source(
    db: InfrahubDatabase, default_branch, criticality_schema, first_account, second_account
):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4, _source=first_account)
    await obj1.save(db=db)

    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(
        db=db,
        name="medium",
        level={"value": 3, "source": second_account.id},
        description="My desc",
        color="#333333",
        _source=first_account,
    )
    await obj2.save(db=db)

    default_branch = await registry.get_branch(db=db, branch="main")

    query = await NodeListGetAttributeQuery.init(
        db=db, ids=[obj1.id, obj2.id], branch=default_branch, include_source=True
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == sorted([obj1.id, obj2.id])
    assert (
        query.get_attributes_group_by_node()[obj1.id].attrs["name"].node_properties["source"].uuid == first_account.id
    )
    assert (
        query.get_attributes_group_by_node()[obj2.id].attrs["level"].node_properties["source"].uuid == second_account.id
    )
    assert (
        query.get_attributes_group_by_node()[obj2.id].attrs["name"].node_properties["source"].uuid == first_account.id
    )


async def test_query_NodeListGetAttributeQuery(db: InfrahubDatabase, base_dataset_02):
    default_branch = await registry.get_branch(db=db, branch="main")
    branch1 = await registry.get_branch(db=db, branch="branch1")

    # Query all the nodes in main but only c1 and c2 present
    # Expect 2 attributes per node(x2) = 4 attributes
    query = await NodeListGetAttributeQuery.init(
        db=db, ids=["c1", "c2", "c3"], branch=default_branch, fields={"name": True, "is_electric": True}
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2"]
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 2
    assert len(query.get_attributes_group_by_node()["c2"].attrs) == 2
    assert len(list(query.get_results())) == 4

    # Query all the nodes in branch1: c1, c2 and c3 present
    # Expect 6 attributes because each node has 1 but c1at2 has its value and its protected flag defined both in Main and Branch1
    query = await NodeListGetAttributeQuery.init(
        db=db, ids=["c1", "c2", "c3"], branch=branch1, fields={"nbr_seats": True}
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2", "c3"]
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 1
    assert len(query.get_attributes_group_by_node()["c2"].attrs) == 1
    assert len(query.get_attributes_group_by_node()["c3"].attrs) == 1
    assert len(list(query.get_results())) == 6

    # Query c1 in branch1
    # Expect 4 attributes because c1at2 has its value and its protected flag defined both in Main and Branch1
    query = await NodeListGetAttributeQuery.init(db=db, ids=["c1"], branch=branch1, fields={"nbr_seats": True})
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1"]
    assert len(list(query.get_results())) == 4
    assert query.results[0].branch_score != query.results[1].branch_score

    # Query all the nodes in branch1 in isolated mode, only c1 and c3 present
    # Expect 4 attributes because c1at2 has its value and its protected flag defined both in Main and Branch1
    branch1.is_isolated = True
    query = await NodeListGetAttributeQuery.init(db=db, ids=["c1"], branch=branch1, fields={"nbr_seats": True})
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1"]
    assert len(list(query.get_results())) == 4
    assert query.results[0].branch_score != query.results[1].branch_score


async def test_query_NodeListGetAttributeQuery_deleted(db: InfrahubDatabase, base_dataset_02):
    default_branch = await registry.get_branch(db=db, branch="main")
    branch1 = await registry.get_branch(db=db, branch="branch1")

    schema = registry.schema.get_schema_branch(name=branch1.name)
    car_schema = schema.get(name="TestCar")

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=car_schema,
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="is_electric"),
    )
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=branch1, migration=migration)
    await query.execute(db=db)

    # Query all the nodes in main but only c1 and c2 present
    # Expect 2 attributes per node(x2) = 4 attributes
    query = await NodeListGetAttributeQuery.init(
        db=db,
        ids=["c1", "c2", "c3"],
        branch=default_branch,
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2"]

    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 4
    assert len(query.get_attributes_group_by_node()["c2"].attrs) == 4

    # Query all the nodes in branch1: c1, c2 and c3 present
    # Expect 6 attributes because each node has 1 but c1at2 has its value and its protected flag defined both in Main and Branch1
    query = await NodeListGetAttributeQuery.init(db=db, ids=["c1", "c2", "c3"], branch=branch1)
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2", "c3"]
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 3
    assert len(query.get_attributes_group_by_node()["c2"].attrs) == 3
    assert len(query.get_attributes_group_by_node()["c3"].attrs) == 3

    # Query c1 in branch1
    # Expect 4 attributes because c1at2 has its value and its protected flag defined both in Main and Branch1
    query = await NodeListGetAttributeQuery.init(
        db=db, ids=["c1"], branch=branch1, fields={"nbr_seats": True, "is_electric": True}
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1"]
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 1


async def test_query_NodeListGetRelationshipsQuery(db: InfrahubDatabase, default_branch: Branch, person_jack_tags_main):
    default_branch = await registry.get_branch(db=db, branch="main")
    query = await NodeListGetRelationshipsQuery.init(
        db=db,
        ids=[person_jack_tags_main.id],
        branch=default_branch,
    )
    await query.execute(db=db)
    result = query.get_peers_group_by_node()
    assert person_jack_tags_main.id in result
    assert "builtintag__testperson" in result[person_jack_tags_main.id]
    assert len(result[person_jack_tags_main.id]["builtintag__testperson"]) == 2


async def test_query_NodeDeleteQuery(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_jack_tags_main: Node,
    tag_blue_main: Node,
):
    tags_before = await NodeManager.query(db=db, schema=InfrahubKind.TAG, branch=default_branch)

    query = await NodeDeleteQuery.init(db=db, node=tag_blue_main, branch=default_branch)
    await query.execute(db=db)

    tags_after = await NodeManager.query(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    assert len(tags_after) == len(tags_before) - 1


async def test_query_NodeGetHierarchyQuery_ancestors(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_location_data,
):
    node_schema = registry.schema.get(name="LocationRack", branch=default_branch)

    europe = hierarchical_location_data["europe"]
    paris = hierarchical_location_data["paris"]
    paris_r1 = hierarchical_location_data["paris-r1"]

    query = await NodeGetHierarchyQuery.init(
        db=db,
        direction=RelationshipHierarchyDirection.ANCESTORS,
        node_id=paris_r1.id,
        node_schema=node_schema,
        branch=default_branch,
    )
    await query.execute(db=db)
    assert sorted(list(query.get_peer_ids())) == sorted([paris.id, europe.id])


async def test_query_NodeGetHierarchyQuery_filters(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_location_data: Dict[str, Node],
):
    node_schema = registry.schema.get(name="LocationRack", branch=default_branch)

    europe = hierarchical_location_data["europe"]

    ids_to_names = {value.id: value for _, value in hierarchical_location_data.items()}

    query = await NodeGetHierarchyQuery.init(
        db=db,
        direction=RelationshipHierarchyDirection.DESCENDANTS,
        node_id=europe.id,
        filters={"descendants__status__value": "online"},
        node_schema=node_schema,
        branch=default_branch,
    )

    await query.execute(db=db)
    descendants_ids = list(query.get_peer_ids())
    descendants_names = [ids_to_names[descendants_id].name.value for descendants_id in descendants_ids]

    assert sorted(descendants_names) == ["london", "london-r1", "paris", "paris-r1"]
