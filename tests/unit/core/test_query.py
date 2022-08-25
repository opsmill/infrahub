import pendulum
import pytest

from infrahub.core.query import Query
from infrahub.core.utils import delete_all_nodes
from infrahub.database import execute_write_query


class Query01(Query):
    def query_init(self):
        query = """
        MATCH (n) WHERE n.uuid = $uuid
        MATCH (n)-[r1]-(at:Attribute)-[r2]-(av)
        """

        self.return_labels = ["n", "at", "av", "r1", "r2"]
        self.params["uuid"] = "5ffa45d4"

        self.add_to_query(query)


def test_query_base():

    query = Query01()
    expected_query = "MATCH (n) WHERE n.uuid = $uuid\nMATCH (n)-[r1]-(at:Attribute)-[r2]-(av)\nRETURN n,at,av,r1,r2"

    assert query.get_query() == expected_query


def test_query_results(simple_dataset_01):

    query = Query01()

    assert query.has_been_executed == False
    query.execute()

    assert query.has_been_executed == True

    assert query.num_of_results == 3
    assert query.results[0].get("at") is not None
