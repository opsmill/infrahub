from collections.abc import Generator

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.manager import GraphQLSchemaManager
from infrahub.graphql.registry import registry as graphql_registry


class HashCountingGenericSchema(GenericSchema):
    """A generic schema that records how many times its hash is computed."""

    _hash_computations: int = 0

    def get_hash(self, display_values: bool = False) -> str:
        self._hash_computations += 1
        return super().get_hash(display_values=display_values)


class HashCountingNodeSchema(NodeSchema):
    """A node schema that records how many times its hash is computed."""

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


def test_full_build_computes_the_hash_of_a_node_schema_once() -> None:
    schema_branch = SchemaBranch(cache={}, name="main")
    schema_branch.load_schema(schema=SchemaRoot(**internal_schema))
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    tag_data = schema_branch.get_node(name=InfrahubKind.TAG).model_dump()
    # The description differs, because the branch keeps the schema it already holds for a given hash.
    tag_schema = HashCountingNodeSchema(**tag_data | {"description": "Tag with a hash counter"})
    schema_branch.set(name=InfrahubKind.TAG, schema=tag_schema)
    tag_schema._hash_computations = 0

    GraphQLSchemaManager(schema=schema_branch).generate()

    assert tag_schema._hash_computations == 1
