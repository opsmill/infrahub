from __future__ import annotations

import copy
from typing import Any

import pytest


@pytest.fixture(scope="class")
def schema_animal_generic() -> dict[str, Any]:
    """Generic Animal without namespace restriction."""
    return {
        "name": "Animal",
        "namespace": "Testing",
        "label": "Animal",
        "order_by": ["name__value"],
        "display_labels": ["name__value"],
        "attributes": [
            {"name": "name", "kind": "Text"},
            {"name": "description", "kind": "Text", "optional": True},
        ],
    }


@pytest.fixture(scope="class")
def schema_animal_generic_restricted_to_dog(schema_animal_generic: dict[str, Any]) -> dict[str, Any]:
    """Generic Animal with restricted_namespaces allowing only Dog namespace."""
    schema = copy.deepcopy(schema_animal_generic)
    schema["restricted_namespaces"] = ["Dog"]
    return schema


@pytest.fixture(scope="class")
def schema_animal_generic_restricted_to_cat(schema_animal_generic: dict[str, Any]) -> dict[str, Any]:
    """Generic Animal with restricted_namespaces allowing only Cat namespace."""
    schema = copy.deepcopy(schema_animal_generic)
    schema["restricted_namespaces"] = ["Cat"]
    return schema


@pytest.fixture(scope="class")
def schema_dog_node() -> dict[str, Any]:
    """Dog node in Dog namespace, inheriting from Animal generic."""
    return {
        "name": "Dog",
        "namespace": "Dog",
        "label": "Dog",
        "display_labels": ["name__value"],
        "inherit_from": ["TestingAnimal"],
        "attributes": [
            {"name": "breed", "kind": "Text", "optional": True},
        ],
    }


@pytest.fixture(scope="class")
def schema_cat_node() -> dict[str, Any]:
    """Cat node in Cat namespace, inheriting from Animal generic (violates Dog restriction)."""
    return {
        "name": "Cat",
        "namespace": "Cat",
        "label": "Cat",
        "display_labels": ["name__value"],
        "inherit_from": ["TestingAnimal"],
        "attributes": [
            {"name": "color", "kind": "Text", "optional": True},
        ],
    }
