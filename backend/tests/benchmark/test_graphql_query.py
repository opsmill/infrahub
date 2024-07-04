import os

import pytest
from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params
from infrahub.test_data.dataset04 import load_data

NBR_WARMUP = int(os.getenv("INFRAHUB_BENCHMARK_NBR_WARMUP", 5))


@pytest.fixture
async def dataset04(db: InfrahubDatabase, default_branch, register_default_schema):
    await load_data(db=db, nbr_query=250)


def test_query_one_model(exec_async, aio_benchmark, db: InfrahubDatabase, default_branch: Branch, dataset04):
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

    for _ in range(NBR_WARMUP):
        exec_async(
            graphql,
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

    aio_benchmark(
        graphql,
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )


def test_query_rel_many(exec_async, aio_benchmark, db: InfrahubDatabase, default_branch: Branch, dataset04):
    query = """
    query {
        InfraDevice {
            edges {
                node {
                    name {
                        value
                    }
                    interfaces {
                        edges {
                            node {
                                name {
                                    value
                                }
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

    for _ in range(NBR_WARMUP):
        exec_async(
            graphql,
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

    aio_benchmark(
        graphql,
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )


def test_query_rel_one(exec_async, aio_benchmark, db: InfrahubDatabase, default_branch: Branch, dataset04):
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

    for _ in range(NBR_WARMUP):
        exec_async(
            graphql,
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

    aio_benchmark(
        graphql,
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )


# @pytest.mark.xfail(reason="Disabling for now but it's not producing consistent results")
# def test_query_rel_one_filter_rel_many(aio_benchmark, db: InfrahubDatabase, default_branch: Branch, dataset04):
#     query = """
#     query GetTags {
#         CoreGraphQLQuery(tags__name__value: "yellow") {
#             count
#             edges {
#                 node {
#                     id
#                     display_label
#                     repository {
#                         node {
#                             id
#                             name {
#                                 value
#                             }
#                         }
#                     }
#                 }
#             }
#         }
#     }
#     """

#     gql_params = prepare_graphql_params(
#         db=db, include_mutation=False, include_subscription=False, branch=default_branch
#     )
#     aio_benchmark(
#         graphql,
#         schema=gql_params.schema,
#         source=query,
#         context_value=gql_params.context,
#         root_value=None,
#         variable_values={},
#     )
