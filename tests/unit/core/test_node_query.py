from infrahub.core import get_branch
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetLocalAttributeValueQuery, NodeListGetAttributeQuery
from infrahub.core.timestamp import Timestamp


def test_query_NodeListGetLocalAttributeValueQuery(default_branch, car_person_schema):

    p1 = Node("Person").new(name="John", height=180).save()
    car1 = Node("Car").new(name="accord", nbr_seats=5, is_electric=False, owner=p1).save()
    car2 = Node("Car").new(name="model3", nbr_seats=5, is_electric=True, owner=p1).save()

    ids = [
        car1.name.db_id,
        car1.nbr_seats.db_id,
        car1.is_electric.db_id,
        car1.color.db_id,
        car2.name.db_id,
        car2.nbr_seats.db_id,
        car2.is_electric.db_id,
        car2.color.db_id,
    ]

    query = NodeListGetLocalAttributeValueQuery(ids, branch=default_branch, at=Timestamp()).execute()
    assert len(query.get_results_by_id()) == 8


def test_query_NodeListGetAttributeQuery_all_fields(base_dataset_02, car_person_schema):

    default_branch = get_branch("main")
    branch1 = get_branch("branch1")

    # Query all the nodes in main but only c1 and c2 present
    # Expect 3 attributes per node(x2) = 6 attributes
    query = NodeListGetAttributeQuery(ids=["c1", "c2", "c3"], branch=default_branch).execute()
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2"]
    assert len(list(query.get_results())) == 6
    assert len(query.get_attributes_group_by_node()["c1"]["attrs"]) == 3
    assert len(query.get_attributes_group_by_node()["c2"]["attrs"]) == 3

    # Query all the nodes in branch1, only c1 and c3 present
    # Expect 7 attributes because each node has 3 but c1at2 has a value both in Main and Branch1
    query = NodeListGetAttributeQuery(ids=["c1", "c2", "c3"], branch=branch1).execute()
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c3"]
    assert len(list(query.get_results())) == 7
    assert len(query.get_attributes_group_by_node()["c1"]["attrs"]) == 3
    assert len(query.get_attributes_group_by_node()["c3"]["attrs"]) == 3


def test_query_NodeListGetAttributeQuery_with_source(default_branch, criticality_schema, first_account, second_account):

    obj1 = Node(criticality_schema).new(name="low", level=4, _source=first_account).save()
    obj2 = (
        Node(criticality_schema)
        .new(
            name="medium",
            level={"value": 3, "source": second_account.id},
            description="My desc",
            color="#333333",
            _source=first_account,
        )
        .save()
    )

    default_branch = get_branch("main")

    query = NodeListGetAttributeQuery(ids=[obj1.id, obj2.id], branch=default_branch, include_source=True).execute()
    assert sorted(query.get_attributes_group_by_node().keys()) == sorted([obj1.id, obj2.id])
    assert query.get_attributes_group_by_node()[obj1.id]["attrs"]["name"].source_uuid == first_account.id
    assert query.get_attributes_group_by_node()[obj2.id]["attrs"]["level"].source_uuid == second_account.id
    assert query.get_attributes_group_by_node()[obj2.id]["attrs"]["name"].source_uuid == first_account.id


def test_query_NodeListGetAttributeQuery(base_dataset_02, car_person_schema):

    default_branch = get_branch("main")
    branch1 = get_branch("branch1")

    # Query all the nodes in main but only c1 and c2 present
    # Expect 2 attributes per node(x2) = 4 attributes
    query = NodeListGetAttributeQuery(
        ids=["c1", "c2", "c3"], branch=default_branch, fields={"name": True, "is_electric": True}
    ).execute()
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2"]
    assert len(query.get_attributes_group_by_node()["c1"]["attrs"]) == 2
    assert len(query.get_attributes_group_by_node()["c2"]["attrs"]) == 2
    assert len(list(query.get_results())) == 4

    # Query all the nodes in branch1, only c1 and c3 present
    # Expect 3 attributes because each node has 1 but c1at2 has a value both in Main and Branch1
    query = NodeListGetAttributeQuery(ids=["c1", "c2", "c3"], branch=branch1, fields={"nbr_seats": True}).execute()
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c3"]
    assert len(query.get_attributes_group_by_node()["c1"]["attrs"]) == 1
    assert len(query.get_attributes_group_by_node()["c3"]["attrs"]) == 1
    assert len(list(query.get_results())) == 3

    # Query all the nodes in branch1, only c1 and c3 present
    # Expect 3 attributes because each node has 1 but c1at2 has a value both in Main and Branch1
    query = NodeListGetAttributeQuery(ids=["c1"], branch=branch1, fields={"nbr_seats": True}).execute()
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1"]
    assert len(list(query.get_results())) == 2
    assert query.results[0].branch_score != query.results[1].branch_score
