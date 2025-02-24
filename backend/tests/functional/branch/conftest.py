from typing import Any

import pytest
from infrahub_sdk.schema import BranchSupportType


@pytest.fixture(scope="class")
def car_person_branch_agnostic_schema() -> dict[str, Any]:
    schema: dict[str, Any] = {
        "version": "1.0",
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "uniqueness_constraints": [["name__value"]],
                "branch": BranchSupportType.AGNOSTIC.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "label": "Commander of Car",
                        "peer": "TestPerson",
                        "optional": False,
                        "kind": "Parent",
                        "cardinality": "one",
                        "direction": "outbound",
                        "branch": BranchSupportType.AGNOSTIC.value,
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
                ],
                "relationships": [
                    {
                        "name": "cars",
                        "peer": "TestCar",
                        "cardinality": "many",
                        "direction": "inbound",
                        "branch": BranchSupportType.AGNOSTIC.value,
                    }
                ],
            },
            {
                "name": "Roofrack",
                "namespace": "Test",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "size", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "car",
                        "label": "Commander of Car",
                        "peer": "TestCar",
                        "optional": False,
                        "kind": "Parent",
                        "cardinality": "one",
                        "direction": "outbound",
                        "branch": BranchSupportType.AGNOSTIC.value,
                    },
                ],
            },
        ],
    }
    return schema
