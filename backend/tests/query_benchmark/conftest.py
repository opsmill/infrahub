from pathlib import Path
from typing import Any

import pytest

from infrahub.core.constants import BranchSupportType
from infrahub.core.schema import SchemaRoot
from tests.helpers.query_benchmark.db_query_profiler import GraphProfileGenerator

RESULTS_FOLDER = Path(__file__).resolve().parent / "query_performance_results"


@pytest.fixture
async def car_person_schema_root() -> SchemaRoot:
    schema: dict[str, Any] = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "uniqueness_constraints": [["name__value"]],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number", "optional": True},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7, "optional": True},
                    {"name": "is_electric", "kind": "Boolean", "optional": True},
                    {
                        "name": "transmission",
                        "kind": "Text",
                        "optional": True,
                        "enum": ["manual", "automatic", "flintstone-feet"],
                    },
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "label": "Commander of Car",
                        "peer": "TestPerson",
                        "cardinality": "one",
                    },
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "branch": BranchSupportType.AWARE.value,
                "uniqueness_constraints": [["name__value"]],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [
                    {"name": "cars", "peer": "TestCar", "cardinality": "many"},
                ],
            },
        ],
    }

    return SchemaRoot(**schema)


@pytest.fixture(scope="session")
async def graph_generator() -> GraphProfileGenerator:
    """
    Use GraphProfileGenerator as a fixture as it may allow to properly generate graphs from
    distinct tests, instead of having each test managing its own display.
    """

    return GraphProfileGenerator()
