"""Integration tests for restricted_namespaces validation.

These tests verify that changing restricted_namespaces on a generic
is properly validated when existing nodes would violate the new restriction.
"""

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.integration.schema_lifecycle.shared import TestSchemaLifecycleBase
from tests.integration.shared import load_schema


class TestRestrictedNamespacesValidation(TestSchemaLifecycleBase):
    """Test that modifying restricted_namespaces is validated against existing nodes."""

    async def test_change_restriction_should_fail(
        self,
        initial_dataset: dict[str, str],
        schema_with_cat_restriction: dict[str, Any],
    ) -> None:
        """Test that changing restricted_namespaces is rejected when existing nodes violate the new restriction.

        Scenario:
        - Initial: generic Animal (restricted_namespaces: ["Dog"]) and node Dog
        - Update: Animal's restricted_namespaces changed to ["Cat"]
        - Expected: Validation fails because Dog node (namespace: Dog) doesn't comply
        """
        schema_branch: SchemaBranch = registry.schema.get_schema_branch(name=registry.default_branch)

        # The validation happens during schema processing when a node inherits from a generic
        # with restricted_namespaces that doesn't include the node's namespace
        with pytest.raises(ValueError, match=r"(?s)restricted namespaces(?=.*Dog)(?=.*Cat)"):
            candidate_schema: SchemaBranch = schema_branch.duplicate()
            candidate_schema.load_schema(schema=SchemaRoot(**schema_with_cat_restriction))
            candidate_schema.process()

    # Fixtures

    @pytest.fixture(scope="class")
    def schema_with_dog_restriction(
        self,
        schema_animal_generic_restricted_to_dog: dict[str, Any],
        schema_dog_node: dict[str, Any],
    ) -> dict[str, Any]:
        """Schema where Animal generic allows Dog namespace."""
        return {
            "version": "1.0",
            "generics": [schema_animal_generic_restricted_to_dog],
            "nodes": [schema_dog_node],
        }

    @pytest.fixture(scope="class")
    def schema_with_cat_restriction(
        self,
        schema_animal_generic_restricted_to_cat: dict[str, Any],
        schema_dog_node: dict[str, Any],
    ) -> dict[str, Any]:
        """Schema where Animal generic allows only Cat namespace.

        This should fail validation when Dog node (namespace: Dog) exists.
        """
        return {
            "version": "1.0",
            "generics": [schema_animal_generic_restricted_to_cat],
            "nodes": [schema_dog_node],
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        schema_with_dog_restriction: dict[str, Any],
    ) -> dict[str, str]:
        """Create initial schema and a Dog instance."""
        await load_schema(db=db, schema=schema_with_dog_restriction)

        # Create a Dog instance
        dog: Node = await Node.init(schema="DogDog", db=db)
        await dog.new(db=db, name="Yann", breed="Brittany Spaniel")
        await dog.save(db=db)

        return {"dog": dog.id}
