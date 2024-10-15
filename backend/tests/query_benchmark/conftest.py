import pytest

from infrahub.core.schema import SchemaRoot
from tests.helpers.query_benchmark.db_query_profiler import QueryAnalyzer


@pytest.fixture(scope="session")
def query_analyzer() -> QueryAnalyzer:
    return QueryAnalyzer()


@pytest.fixture
def car_person_schema_root() -> SchemaRoot:
    schema = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "nbr_seats__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                ],
                "relationships": [
                    {"name": "owner", "peer": "TestPerson", "optional": True, "cardinality": "one"},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "order_by": ["height__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "TestCar", "cardinality": "many"}],
            },
        ],
    }

    return SchemaRoot(**schema)  # type: ignore[arg-type]
