"""Integration test for restricted_namespaces validation across branches.

Verifies that the schema integrity check catches namespace restriction violations
when schema changes are split across branches:
- Main branch: adds restricted_namespaces to a generic
- Feature branch: adds a node inheriting from the generic with a non-compliant namespace

The candidate schema (merge of both) must fail validation during process().
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.schema import SchemaRoot

from ..shared import load_schema
from .shared import TestSchemaLifecycleBase

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestRestrictedNamespacesCrossBranch(TestSchemaLifecycleBase):
    """Test that merging schemas from two branches detects restricted_namespaces violations.

    Scenario:
    1. Load initial schema: generic Animal (no restriction) + DogDog node
    2. On main: add restricted_namespaces: ["Dog"] to Animal
    3. On branch: add CatCat node (namespace: Cat, inherits Animal)
    4. Build candidate schema (main + branch) and process() -> should raise ValueError
    """

    @pytest.fixture(scope="class")
    def schema_initial(
        self,
        schema_animal_generic: dict[str, Any],
        schema_dog_node: dict[str, Any],
    ) -> dict[str, Any]:
        """Initial schema: generic without restriction + one compliant node."""
        return {
            "version": "1.0",
            "generics": [schema_animal_generic],
            "nodes": [schema_dog_node],
        }

    @pytest.fixture(scope="class")
    def schema_main_with_restriction(
        self,
        schema_animal_generic_restricted_to_dog: dict[str, Any],
        schema_dog_node: dict[str, Any],
    ) -> dict[str, Any]:
        """Main branch schema: generic now has restricted_namespaces: [Dog]."""
        return {
            "version": "1.0",
            "generics": [schema_animal_generic_restricted_to_dog],
            "nodes": [schema_dog_node],
        }

    @pytest.fixture(scope="class")
    def schema_branch_with_cat(
        self,
        schema_animal_generic: dict[str, Any],
        schema_dog_node: dict[str, Any],
        schema_cat_node: dict[str, Any],
    ) -> dict[str, Any]:
        """Branch schema: adds Cat node (non-compliant namespace)."""
        return {
            "version": "1.0",
            "generics": [schema_animal_generic],
            "nodes": [schema_dog_node, schema_cat_node],
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        schema_initial: dict[str, Any],
    ) -> None:
        await load_schema(db=db, schema=schema_initial)

    async def test_cross_branch_merge_detects_namespace_violation(
        self,
        initial_dataset: None,
        schema_main_with_restriction: dict[str, Any],
        schema_branch_with_cat: dict[str, Any],
    ) -> None:
        """Simulate the proposed change schema integrity check.

        Build a candidate schema the same way run_proposed_change_schema_integrity_check does:
        - dest_schema = main branch schema (with restricted_namespaces on the generic)
        - source_schema = feature branch schema (with the violating Cat node)
        - candidate = dest_schema.update(source_schema)
        - candidate.process() should raise ValueError about namespace restriction
        """
        # Simulate main branch: load schema with restriction
        main_schema: SchemaBranch = registry.schema.get_schema_branch(name=registry.default_branch).duplicate()
        main_schema.load_schema(schema=SchemaRoot(**schema_main_with_restriction))

        # Simulate feature branch: load schema with non-compliant node
        branch_schema: SchemaBranch = registry.schema.get_schema_branch(name=registry.default_branch).duplicate()
        branch_schema.load_schema(schema=SchemaRoot(**schema_branch_with_cat))

        # Build candidate schema the way the proposed change integrity check does:
        # candidate_schema = dest_schema.duplicate(); candidate_schema.update(schema=source_schema)
        candidate_schema = main_schema.duplicate()
        candidate_schema.update(schema=branch_schema)

        # This must detect the violation: CatCat (namespace: Cat)
        # inherits from TestingAnimal which has restricted_namespaces: ["Dog"]
        with pytest.raises(ValueError, match=r"restricted namespaces.*Cat"):
            candidate_schema.duplicate().process()
