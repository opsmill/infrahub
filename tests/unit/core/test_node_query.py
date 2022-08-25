from infrahub.core.node import Node
from infrahub.core.node.query import NodeListGetLocalAttributeValueQuery
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
