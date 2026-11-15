from collections.abc import Generator

import pytest

from infrahub.core.schema import GenericSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.manager import GraphQLSchemaManager
from infrahub.graphql.registry import registry as graphql_registry


class HashCountingGenericSchema(GenericSchema):
    """A generic schema that records how many times its hash is computed."""

    _hash_computations: int = 0

    def get_hash(self, display_values: bool = False) -> str:
        self._hash_computations += 1
        return super().get_hash(display_values=display_values)


@pytest.fixture(autouse=True)
def clear_registered_types() -> Generator[None, None, None]:
    yield
    graphql_registry.clear_cache()


def make_manager() -> GraphQLSchemaManager:
    return GraphQLSchemaManager(schema=SchemaBranch(cache={}, name="main"))


def test_schema_hash_is_computed_once_per_schema_object() -> None:
    manager = make_manager()
    schema = HashCountingGenericSchema(name="Vehicle", namespace="Test")

    first = manager.generate_interface_object(schema=schema)
    second = manager.generate_interface_object(schema=schema)

    assert first.reference_hash == second.reference_hash
    assert schema._hash_computations == 1


def test_schemas_of_the_same_kind_keep_their_own_hash() -> None:
    manager = make_manager()
    first_schema = GenericSchema(name="Vehicle", namespace="Test", description="First definition")
    second_schema = GenericSchema(name="Vehicle", namespace="Test", description="Second definition")

    first = manager.generate_interface_object(schema=first_schema)
    second = manager.generate_interface_object(schema=second_schema)

    assert first.reference_hash != second.reference_hash
