from infrahub.core import branch, get_branch
from infrahub.core.node import Node
from infrahub.core.node.query import NodeListGetLocalAttributeValueQuery, NodeListGetAttributeQuery
from infrahub.core.timestamp import Timestamp
from tests.unit.conftest import default_branch


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
