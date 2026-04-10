import copy

import pytest

from infrahub.core.schema import GenericSchema, SchemaRoot
from infrahub.core.schema.definitions.core import core_models_mixed
from infrahub.core.schema.schema_branch import SchemaBranch


class TestNamespaceRestrictionInvalidCases:
    async def test_generic_schema_with_restricted_namespace_fails_if_required(
        self,
        correct_schema_generic_with_namespace_restriction: SchemaRoot,
    ) -> None:
        # Retrieve the schema and make it incorrect
        test_schema = correct_schema_generic_with_namespace_restriction
        test_schema.nodes[0].namespace = "NotACorrectNamespace"

        schema = SchemaBranch(cache={}, name="test")
        schema.load_schema(schema=test_schema)

        # Act
        with pytest.raises(ValueError, match="does not comply with this restriction as its namespace"):
            schema.validate_restricted_namespaces_from_generic()

    async def test_generic_schema_with_empty_restricted_namespace_is_failing(
        self,
        correct_schema_generic_with_namespace_restriction: SchemaRoot,
    ) -> None:
        # Retrieve the schema and make the namespaces allowed list empty
        test_schema = correct_schema_generic_with_namespace_restriction
        test_schema.generics[0].restricted_namespaces = []

        schema = SchemaBranch(cache={}, name="test")
        schema.load_schema(schema=test_schema)

        # Act
        with pytest.raises(ValueError, match="does not comply with this restriction as its namespace"):
            schema.validate_restricted_namespaces_from_generic()

    async def test_restricted_namespaces_enforced_with_multi_generic_inheritance(
        self,
        schema_multi_generic_with_one_restricted: SchemaRoot,
    ) -> None:
        """When a node inherits from multiple generics and only one has restricted_namespaces,
        the restriction from that generic must still be enforced."""
        schema = SchemaBranch(cache={}, name="test")
        schema.load_schema(schema=schema_multi_generic_with_one_restricted)

        with pytest.raises(ValueError, match="does not comply with this restriction as its namespace") as error:
            schema.validate_restricted_namespaces_from_generic()

        assert "CoreGenericA" in str(error.value)

    async def test_schema_loading_when_node_inherits_from_core_repository(
        self,
        incorrect_schema_inherits_from_generic_core_repository: SchemaRoot,
    ) -> None:
        test_schema = copy.deepcopy(incorrect_schema_inherits_from_generic_core_repository)
        generic_schemas: list[GenericSchema] = core_models_mixed["generics"]

        schema = SchemaBranch(cache={}, name="test")
        for generic_schema in generic_schemas:
            schema.load_schema(schema=SchemaRoot(generics=[generic_schema], nodes=[]))
        schema.load_schema(schema=test_schema)

        with pytest.raises(ValueError, match="Generic node 'CoreGenericRepository' has restricted namespaces"):
            schema.validate_restricted_namespaces_from_generic()


class TestNamespaceRestrictionValidCases:
    async def test_generic_schema_with_restricted_namespace_pass_if_same_namespace(
        self,
        correct_schema_generic_with_namespace_restriction: SchemaRoot,
    ) -> None:
        schema = SchemaBranch(cache={}, name="test")
        schema.load_schema(schema=correct_schema_generic_with_namespace_restriction)

        schema.validate_restricted_namespaces_from_generic()

        assert schema.all_names == ["AnimalDog", "AnimalGeneric"]
