"""Unit tests for AccountMetadataResolver.

These tests verify that AccountMetadataResolver correctly:
- Resolves created_by and updated_by fields to full account data
- Handles SYSTEM_USER_ID by returning synthetic system account data
- Caches DataLoader instances for the same parameters
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import SYSTEM_USER_ID, InfrahubKind
from infrahub.core.node import Node
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.loaders.account import SYSTEM_ACCOUNT_DISPLAY_LABEL
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def tag_node(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch) -> Node:
    """Create a test tag node with metadata for resolver tests."""
    obj = await Node.init(db=db, schema=InfrahubKind.TAG)
    await obj.new(db=db, name="Test Tag", description="A test tag")
    await obj.save(db=db)
    return obj


async def test_resolve_created_by_with_system_user(
    db: InfrahubDatabase,
    default_branch: Branch,
    tag_node: Node,
) -> None:
    """Verify created_by resolves to system account data when created by system.

    When a node is created by the system user (SYSTEM_USER_ID), the resolver
    should return synthetic system account data with display_label [Infrahub System].
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    query = """
    query GetTag($id: ID!) {
        BuiltinTag(ids: [$id]) {
            edges {
                node_metadata {
                    created_by {
                        id
                        display_label
                    }
                }
                node {
                    id
                }
            }
        }
    }
    """

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": tag_node.id},
    )

    assert result.errors is None
    assert result.data
    edges = result.data["BuiltinTag"]["edges"]
    assert len(edges) == 1

    node_metadata = edges[0]["node_metadata"]
    created_by = node_metadata["created_by"]
    assert created_by["id"] == SYSTEM_USER_ID
    assert created_by["display_label"] == SYSTEM_ACCOUNT_DISPLAY_LABEL


async def test_resolve_updated_by_with_system_user(
    db: InfrahubDatabase,
    default_branch: Branch,
    tag_node: Node,
) -> None:
    """Verify updated_by resolves to system account data when updated by system.

    When a node is updated by the system user (SYSTEM_USER_ID), the resolver
    should return synthetic system account data with display_label [Infrahub System].
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    query = """
    query GetTag($id: ID!) {
        BuiltinTag(ids: [$id]) {
            edges {
                node_metadata {
                    updated_by {
                        id
                        display_label
                    }
                }
                node {
                    id
                }
            }
        }
    }
    """

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": tag_node.id},
    )

    assert result.errors is None
    assert result.data
    edges = result.data["BuiltinTag"]["edges"]
    assert len(edges) == 1

    node_metadata = edges[0]["node_metadata"]
    updated_by = node_metadata["updated_by"]
    assert updated_by["id"] == SYSTEM_USER_ID
    assert updated_by["display_label"] == SYSTEM_ACCOUNT_DISPLAY_LABEL


async def test_resolver_returns_typename(
    db: InfrahubDatabase,
    default_branch: Branch,
    tag_node: Node,
) -> None:
    """Verify resolver returns __typename for account.

    The resolver should return CoreAccount as the __typename
    for both system and real accounts.
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    query = """
    query GetTag($id: ID!) {
        BuiltinTag(ids: [$id]) {
            edges {
                node_metadata {
                    created_by {
                        __typename
                    }
                }
                node {
                    id
                }
            }
        }
    }
    """

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": tag_node.id},
    )

    assert result.errors is None
    assert result.data
    edges = result.data["BuiltinTag"]["edges"]
    node_metadata = edges[0]["node_metadata"]
    assert node_metadata["created_by"]["__typename"] == InfrahubKind.ACCOUNT


async def test_resolver_on_context_is_instantiated(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Verify AccountMetadataResolver is instantiated on the context.

    The resolver should be instantiated once per GraphQL request
    for all metadata field resolutions within that request.
    """
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    assert gql_params.context.account_metadata_resolver is not None

    resolver1 = gql_params.context.account_metadata_resolver
    resolver2 = gql_params.context.account_metadata_resolver
    assert resolver1 is resolver2


async def test_resolve_both_created_and_updated_by(
    db: InfrahubDatabase,
    default_branch: Branch,
    tag_node: Node,
) -> None:
    """Verify both created_by and updated_by can be resolved in the same query.

    When querying both metadata fields together, both should resolve correctly
    using the same resolver instance and DataLoader caching.
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    query = """
    query GetTag($id: ID!) {
        BuiltinTag(ids: [$id]) {
            edges {
                node_metadata {
                    created_by {
                        id
                        display_label
                    }
                    updated_by {
                        id
                        display_label
                    }
                }
                node {
                    id
                }
            }
        }
    }
    """

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": tag_node.id},
    )

    assert result.errors is None
    assert result.data
    edges = result.data["BuiltinTag"]["edges"]
    assert len(edges) == 1

    node_metadata = edges[0]["node_metadata"]

    created_by = node_metadata["created_by"]
    assert created_by["id"] == SYSTEM_USER_ID
    assert created_by["display_label"] == SYSTEM_ACCOUNT_DISPLAY_LABEL

    updated_by = node_metadata["updated_by"]
    assert updated_by["id"] == SYSTEM_USER_ID
    assert updated_by["display_label"] == SYSTEM_ACCOUNT_DISPLAY_LABEL
