from graphql import GraphQLSchema
from pytest_benchmark.fixture import BenchmarkFixture

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.manager import GraphQLSchemaManager


def test_graphql_generate_schema(
    benchmark: BenchmarkFixture,
    db: InfrahubDatabase,
    default_branch: Branch,
    data_schema: None,
    car_person_schema: SchemaBranch,
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)
    schema = benchmark(gqlm.generate)

    assert isinstance(schema, GraphQLSchema)
