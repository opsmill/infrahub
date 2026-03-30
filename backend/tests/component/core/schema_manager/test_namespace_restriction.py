import copy

import pytest

from infrahub.core.schema import GenericSchema, SchemaRoot
from infrahub.core.schema.definitions.core import core_models_mixed
from infrahub.core.schema.schema_branch import SchemaBranch


class TestNamespaceRestriction:
    async def test_generic_schema_with_restricted_namespace_fails_if_required(
        self,
        correct_schema_generic_with_namespace_restriction: SchemaRoot,
    ) -> None:
        # Retrieve the schema and make it incorrect
        test_schema = correct_schema_generic_with_namespace_restriction
        test_schema.nodes[0].namespace = "NotACorrectNamespace"

        schema: SchemaBranch = SchemaBranch(cache={}, name="test")
        schema.load_schema(schema=test_schema)

        # Act
        with pytest.raises(ValueError) as error:
            schema.validate_restricted_namespaces_from_generic()

        assert "does not comply with this restriction as its namespace" in str(error.value)

    async def test_generic_schema_with_empty_restricted_namespace_is_failing(
        self,
        correct_schema_generic_with_namespace_restriction: SchemaRoot,
    ) -> None:
        # Retrieve the schema and make the namespaces allowed list empty
        test_schema = correct_schema_generic_with_namespace_restriction
        test_schema.generics[0].restricted_namespaces = []

        schema: SchemaBranch = SchemaBranch(cache={}, name="test")
        schema.load_schema(schema=test_schema)

        # Act
        with pytest.raises(ValueError, match="does not comply with this restriction as its namespace"):
            schema.validate_restricted_namespaces_from_generic()

    async def test_generic_schema_with_restricted_namespace_pass_if_same_namespace(
        self,
        correct_schema_generic_with_namespace_restriction: SchemaRoot,
    ) -> None:
        schema = SchemaBranch(cache={}, name="test")
        schema.load_schema(schema=correct_schema_generic_with_namespace_restriction)

        # Act
        try:
            schema.validate_restricted_namespaces_from_generic()

        # Assert - no ValueError
        except ValueError:
            pytest.fail(
                "A ValueError has been raised during process_restricted_namespaces check, however, the schema is correct"
            )
        # Assert - schema is correctly loaded
        assert len(schema.all_names) == 2
        assert schema.all_names[0] == "AnimalDog"
        assert schema.all_names[1] == "AnimalGeneric"

    async def test_schema_loading_when_node_inherits_from_core_repository(
        self,
        incorrect_schema_inherits_from_generic_core_repository: SchemaRoot,
    ) -> None:
        test_schema = copy.deepcopy(incorrect_schema_inherits_from_generic_core_repository)
        generic_schemas: list[GenericSchema] = core_models_mixed["generics"]

        schema: SchemaBranch = SchemaBranch(cache={}, name="test")
        for generic_schema_root in [
            SchemaRoot(
                generics=[generic_schema],
                nodes=[],
            )
            for generic_schema in generic_schemas
        ]:
            schema.load_schema(schema=generic_schema_root)
        schema.load_schema(schema=test_schema)

        # Act
        with pytest.raises(ValueError) as error:
            schema.validate_restricted_namespaces_from_generic()

        assert "Generic node 'CoreGenericRepository' has restricted namespaces: ['Core']" in str(error.value)

    async def test_restricted_namespaces_enforced_with_multi_generic_inheritance(self) -> None:
        """When a node inherits from multiple generics and only one has restricted_namespaces,
        the restriction from that generic must still be enforced."""
        schema_data = {
            "generics": [
                {
                    "name": "GenericA",
                    "namespace": "Core",
                    "display_labels": ["name__value"],
                    "order_by": ["name__value"],
                    "attributes": [{"name": "name", "kind": "Text"}],
                    "restricted_namespaces": ["Core"],
                },
                {
                    "name": "GenericB",
                    "namespace": "Animal",
                    "display_labels": ["name__value"],
                    "order_by": ["name__value"],
                    "attributes": [{"name": "color", "kind": "Text"}],
                },
            ],
            "nodes": [
                {
                    "name": "NodeC",
                    "namespace": "Bad",
                    "attributes": [{"name": "extra", "kind": "Text"}],
                    "inherit_from": ["CoreGenericA", "AnimalGenericB"],
                }
            ],
        }

        schema = SchemaBranch(cache={}, name="test")
        schema.load_schema(schema=SchemaRoot(**schema_data))

        with pytest.raises(ValueError) as error:
            schema.validate_restricted_namespaces_from_generic()

        assert "does not comply with this restriction as its namespace" in str(error.value)
        assert "CoreGenericA" in str(error.value)
