from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.schema import SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.helpers.graphql import graphql
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


SITE_SCHEMA_WITH_PROFILE: dict[str, Any] = {
    "nodes": [
        {
            "name": "SiteWithProfile",
            "namespace": "Test",
            "description": "A site with an optional relationship to a prefix",
            "generate_profile": True,
            "attributes": [
                {"name": "name", "kind": "Text"},
            ],
            "relationships": [
                {
                    "name": "prefix",
                    "peer": "IpamIPPrefix",
                    "kind": "Attribute",
                    "optional": True,
                    "cardinality": "one",
                },
            ],
        },
    ],
}


@pytest.fixture
async def site_schema_with_profile(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_extended_schema: SchemaBranch,
) -> None:
    """Set up a schema with a node that has generate_profile=True and a relationship to an IP prefix."""
    schema = SchemaRoot(**SITE_SCHEMA_WITH_PROFILE)
    await load_schema(db=db, schema=schema)


@pytest.fixture
async def prefix_pool(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
) -> CoreIPPrefixPool:
    """Create an IP prefix pool for testing."""
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="test-pool",
        default_prefix_length=24,
        default_prefix_type="IpamIPPrefix",
        resources=[net140],
        ip_namespace=ns1,
    )
    await pool.save(db=db)
    return pool


async def test_create_profile_with_from_pool_fails(
    db: InfrahubDatabase, default_branch: Branch, site_schema_with_profile: None, prefix_pool: CoreIPPrefixPool
) -> None:
    """Test that creating a profile with from_pool in a relationship fails with a validation error."""
    query = """
    mutation CreateProfile($pool_id: String!) {
        ProfileTestSiteWithProfileCreate(data: {
            profile_name: { value: "test-profile" }
            prefix: {
                from_pool: {
                    id: $pool_id
                }
            }
        }) {
            ok
            object {
                id
            }
        }
    }
    """

    default_branch.update_schema_hash()
    service = await InfrahubServices.new(workflow=WorkflowLocalExecution())
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": prefix_pool.id},
    )

    assert result.errors
    assert "Resource pools cannot be used as the source for relationship values in Profiles" in str(result.errors[0])


async def test_update_profile_with_from_pool_fails(
    db: InfrahubDatabase, default_branch: Branch, site_schema_with_profile: None, prefix_pool: CoreIPPrefixPool
) -> None:
    """Test that updating a profile with from_pool in a relationship fails with a validation error."""
    # First, create a profile without a prefix
    profile_schema = registry.schema.get_profile_schema(name="ProfileTestSiteWithProfile", branch=default_branch)
    profile = await Node.init(db=db, schema=profile_schema, branch=default_branch)
    await profile.new(db=db, profile_name="test-profile")
    await profile.save(db=db)

    # Now try to update the profile with a from_pool relationship
    query = """
    mutation UpdateProfile($id: String!, $pool_id: String!) {
        ProfileTestSiteWithProfileUpdate(data: {
            id: $id
            prefix: {
                from_pool: {
                    id: $pool_id
                }
            }
        }) {
            ok
            object {
                id
            }
        }
    }
    """

    default_branch.update_schema_hash()
    service = await InfrahubServices.new(workflow=WorkflowLocalExecution())
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": profile.id, "pool_id": prefix_pool.id},
    )

    assert result.errors
    assert "Resource pools cannot be used as the source for relationship values in Profiles" in str(result.errors[0])


async def test_create_profile_with_direct_peer_succeeds(
    db: InfrahubDatabase,
    default_branch: Branch,
    site_schema_with_profile: None,
    ip_dataset_prefix_v4,
) -> None:
    """Test that creating a profile with a direct peer reference (not from_pool) still works."""
    net142 = ip_dataset_prefix_v4["net142"]

    query = """
    mutation CreateProfile($prefix_id: String!) {
        ProfileTestSiteWithProfileCreate(data: {
            profile_name: { value: "test-profile-direct" }
            prefix: {
                id: $prefix_id
            }
        }) {
            ok
            object {
                id
                profile_name {
                    value
                }
            }
        }
    }
    """

    default_branch.update_schema_hash()
    service = await InfrahubServices.new(workflow=WorkflowLocalExecution())
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"prefix_id": net142.id},
    )

    assert not result.errors
    assert result.data
    assert result.data["ProfileTestSiteWithProfileCreate"]["ok"]
    assert result.data["ProfileTestSiteWithProfileCreate"]["object"]["profile_name"]["value"] == "test-profile-direct"
