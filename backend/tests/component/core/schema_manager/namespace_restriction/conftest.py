from __future__ import annotations

import copy
from typing import Any

import pytest

from infrahub.core.schema import SchemaRoot


@pytest.fixture(scope="class")
def schema_animal_generic() -> dict[str, Any]:
    """Generic Animal without namespace restriction."""
    return {
        "name": "Animal",
        "namespace": "Testing",
        "label": "Animal",
        "order_by": ["name__value"],
        "display_label": "name__value",
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
    """Dog node schema in Dog namespace, inheriting from TestingAnimal."""
    return {
        "name": "Dog",
        "namespace": "Dog",
        "label": "Dog",
        "display_label": "name__value",
        "inherit_from": ["TestingAnimal"],
        "attributes": [
            {"name": "breed", "kind": "Text", "optional": True},
        ],
    }


@pytest.fixture(scope="class")
def schema_cat_node() -> dict[str, Any]:
    """Cat node schema in Cat namespace, inheriting from TestingAnimal (violates namespace restriction)."""
    return {
        "name": "Cat",
        "namespace": "Cat",
        "label": "Cat",
        "display_label": "name__value",
        "inherit_from": ["TestingAnimal"],
        "attributes": [
            {"name": "color", "kind": "Text", "optional": True},
        ],
    }


@pytest.fixture
def correct_schema_generic_with_namespace_restriction() -> SchemaRoot:
    """One generic with namespace restriction and one inherited node, which does follow the namespace restriction rule."""
    return SchemaRoot(
        generics=[
            {
                "name": "Generic",
                "namespace": "Animal",
                "display_label": "name__value",
                "order_by": ["name__value"],
                "attributes": [{"name": "name", "kind": "Text"}],
                "restricted_namespaces": ["Animal"],
            }
        ],
        nodes=[
            {
                "name": "Dog",
                "namespace": "Animal",
                "description": "A dog which follows the animal namespace restriction rule",
                "attributes": [{"name": "dog", "kind": "Text"}],
                "inherit_from": ["AnimalGeneric"],
            }
        ],
    )


@pytest.fixture
def schema_multi_generic_with_one_restricted() -> SchemaRoot:
    """Two generics (one with restricted_namespaces) and a node inheriting both with a wrong namespace."""
    return SchemaRoot(
        generics=[
            {
                "name": "GenericA",
                "namespace": "Core",
                "display_label": "name__value",
                "order_by": ["name__value"],
                "attributes": [{"name": "name", "kind": "Text"}],
                "restricted_namespaces": ["Core"],
            },
            {
                "name": "GenericB",
                "namespace": "Animal",
                "display_label": "name__value",
                "order_by": ["name__value"],
                "attributes": [{"name": "color", "kind": "Text"}],
            },
        ],
        nodes=[
            {
                "name": "NodeC",
                "namespace": "Bad",
                "attributes": [{"name": "extra", "kind": "Text"}],
                "inherit_from": ["CoreGenericA", "AnimalGenericB"],
            }
        ],
    )


@pytest.fixture
def incorrect_schema_inherits_from_generic_core_repository() -> SchemaRoot:
    """One node which inherits from CoreRepository. As the namespace is restricted, this should not be allowed."""
    return SchemaRoot(
        nodes=[
            {
                "name": "ChildrenRepo",
                "namespace": "Child",
                "description": "A repository inheriting from the core generic repository",
                "attributes": [{"name": "children_repository", "kind": "Text"}],
                "inherit_from": ["CoreGenericRepository"],
            }
        ],
    )
