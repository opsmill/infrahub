import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_default_branch,
    create_global_branch,
    create_root_node,
)
from infrahub.core.schema import (
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.core.schema_manager import SchemaBranch, SchemaManager
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params
from infrahub.test_data.dataset04 import load_data


@pytest.fixture(scope="module")
async def reset_environment(db: InfrahubDatabase) -> None:
    registry.delete_all()
    await delete_all_nodes(db=db)
    await create_root_node(db=db)


@pytest.fixture(scope="module")
async def default_branch(reset_environment, db: InfrahubDatabase) -> Branch:
    branch = await create_default_branch(db=db)
    await create_global_branch(db=db)
    registry.schema = SchemaManager()
    return branch


@pytest.fixture(scope="module")
async def register_default_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**internal_schema))
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    default_branch.update_schema_hash()
    await default_branch.save(db=db)
    return schema_branch


@pytest.fixture(scope="module")
async def dataset04(db: InfrahubDatabase, default_branch, register_default_schema):
    await load_data(db=db, nbr_query=250)


def test_query_one_model(aio_benchmark, db: InfrahubDatabase, default_branch: Branch, dataset04):
    query = """
    query {
        CoreGraphQLQuery {
            count
            edges {
                node {
                    id
                    display_label
                    name {
                        value
                    }
                }
            }
        }
    }
    """

    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )

    aio_benchmark(
        graphql,
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )


def test_query_rel_many(aio_benchmark, db: InfrahubDatabase, default_branch: Branch, dataset04):
    query = """
    query {
        CoreGraphQLQuery {
            count
            edges {
                node {
                    id
                    display_label
                    name {
                        value
                    }
                    tags {
                        edges {
                            node {
                                id
                                display_label
                            }
                        }
                    }
                }
            }
        }
    }
    """

    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    aio_benchmark(
        graphql,
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )


def test_query_rel_one(aio_benchmark, db: InfrahubDatabase, default_branch: Branch, dataset04):
    query = """
    query {
        CoreGraphQLQuery {
            count
            edges {
                node {
                    id
                    display_label
                    name {
                        value
                    }
                    repository {
                        node {
                            id
                            name {
                                value
                            }
                        }
                    }
                }
            }
        }
    }
    """

    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    aio_benchmark(
        graphql,
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )


def test_query_rel_one_filter_rel_many(aio_benchmark, db: InfrahubDatabase, default_branch: Branch, dataset04):
    query = """
    query GetTags {
        CoreGraphQLQuery(tags__name__value: "yellow") {
            count
            edges {
                node {
                    id
                    display_label
                    repository {
                        node {
                            id
                            name {
                                value
                            }
                        }
                    }
                }
            }
        }
    }
    """

    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    aio_benchmark(
        graphql,
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
