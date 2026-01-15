"""Tests for GraphQL metadata filtering and ordering functionality.

This module contains tests for:
- Ordering by created_at and updated_at
- Filtering by created_at, updated_at, created_by, updated_by
- Combined metadata filters
- Branch-specific metadata behavior
"""

from dataclasses import dataclass, field
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

# ============================================================================
# Ordering Tests
# ============================================================================


async def test_graphql_order_by_created_at(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> None:
    """Test ordering by created_at in ASC and DESC order via GraphQL."""
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="first", level=1)
    await obj1.save(db=db)

    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="second", level=2)
    await obj2.save(db=db)

    obj3 = await Node.init(db=db, schema=criticality_schema)
    await obj3.new(db=db, name="third", level=3)
    await obj3.save(db=db)

    # Test ASC order
    query_asc = """
    query {
        TestCriticality(order: {node_metadata: {created_at: ASC}}) {
            edges {
                node_metadata { created_at }
                node { name { value } }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result_asc = await graphql(
        schema=gql_params.schema,
        source=query_asc,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result_asc.errors is None
    assert result_asc.data
    edges_asc = result_asc.data["TestCriticality"]["edges"]
    names_asc = [e["node"]["name"]["value"] for e in edges_asc]
    timestamps_asc = [e["node_metadata"]["created_at"] for e in edges_asc]

    assert names_asc == ["first", "second", "third"]
    assert timestamps_asc == sorted(timestamps_asc)

    # Test DESC order
    query_desc = """
    query {
        TestCriticality(order: {node_metadata: {created_at: DESC}}) {
            edges {
                node_metadata { created_at }
                node { name { value } }
            }
        }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result_desc = await graphql(
        schema=gql_params.schema,
        source=query_desc,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result_desc.errors is None
    assert result_desc.data
    edges_desc = result_desc.data["TestCriticality"]["edges"]
    names_desc = [e["node"]["name"]["value"] for e in edges_desc]
    timestamps_desc = [e["node_metadata"]["created_at"] for e in edges_desc]

    assert names_desc == ["third", "second", "first"]
    assert timestamps_desc == sorted(timestamps_desc, reverse=True)


async def test_graphql_order_by_updated_at(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> None:
    """Test ordering by updated_at in ASC and DESC order via GraphQL."""
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="alpha", level=1)
    await obj1.save(db=db)

    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="beta", level=2)
    await obj2.save(db=db)

    obj3 = await Node.init(db=db, schema=criticality_schema)
    await obj3.new(db=db, name="gamma", level=3)
    await obj3.save(db=db)

    # Update in different order: gamma first, then alpha
    obj3_updated = await NodeManager.get_one(db=db, id=obj3.id)
    obj3_updated.level.value = 30  # type: ignore[attr-defined]
    await obj3_updated.save(db=db)

    obj1_updated = await NodeManager.get_one(db=db, id=obj1.id)
    obj1_updated.level.value = 10  # type: ignore[attr-defined]
    await obj1_updated.save(db=db)

    # Expected order by updated_at DESC: alpha (most recent), gamma, beta (never updated)
    query_desc = """
    query {
        TestCriticality(order: {node_metadata: {updated_at: DESC}}) {
            edges {
                node_metadata { updated_at }
                node { name { value } }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result_desc = await graphql(
        schema=gql_params.schema,
        source=query_desc,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result_desc.errors is None
    assert result_desc.data
    edges_desc = result_desc.data["TestCriticality"]["edges"]
    names_desc = [e["node"]["name"]["value"] for e in edges_desc]
    timestamps_desc = [e["node_metadata"]["updated_at"] for e in edges_desc]

    assert names_desc == ["alpha", "gamma", "beta"]
    assert timestamps_desc == sorted(timestamps_desc, reverse=True)

    # Test ASC order
    query_asc = """
    query {
        TestCriticality(order: {node_metadata: {updated_at: ASC}}) {
            edges {
                node_metadata { updated_at }
                node { name { value } }
            }
        }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result_asc = await graphql(
        schema=gql_params.schema,
        source=query_asc,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result_asc.errors is None
    assert result_asc.data
    edges_asc = result_asc.data["TestCriticality"]["edges"]
    names_asc = [e["node"]["name"]["value"] for e in edges_asc]
    timestamps_asc = [e["node_metadata"]["updated_at"] for e in edges_asc]

    assert names_asc == ["beta", "gamma", "alpha"]
    assert timestamps_asc == sorted(timestamps_asc)


async def test_graphql_order_by_metadata_on_user_branch(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> None:
    """Test ordering by created_at and updated_at on a user branch with nodes from both branches."""
    # Create nodes on default branch
    main_obj1 = await Node.init(db=db, schema=criticality_schema)
    await main_obj1.new(db=db, name="main-first", level=1)
    await main_obj1.save(db=db)

    main_obj2 = await Node.init(db=db, schema=criticality_schema)
    await main_obj2.new(db=db, name="main-second", level=2)
    await main_obj2.save(db=db)

    # Create a user branch
    user_branch = await create_branch(branch_name="test-metadata-order-branch", db=db)

    # Create nodes on user branch (these will be created after main branch nodes)
    branch_obj1 = await Node.init(db=db, schema=criticality_schema, branch=user_branch)
    await branch_obj1.new(db=db, name="branch-first", level=10)
    await branch_obj1.save(db=db)

    branch_obj2 = await Node.init(db=db, schema=criticality_schema, branch=user_branch)
    await branch_obj2.new(db=db, name="branch-second", level=20)
    await branch_obj2.save(db=db)

    # Test created_at ASC on user branch - should see main nodes first, then branch nodes
    query_created_asc = """
    query {
        TestCriticality(order: {node_metadata: {created_at: ASC}}) {
            edges {
                node_metadata { created_at }
                node { name { value } }
            }
        }
    }
    """
    user_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=user_branch)
    result_created_asc = await graphql(
        schema=gql_params.schema,
        source=query_created_asc,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result_created_asc.errors is None
    assert result_created_asc.data
    edges_created_asc = result_created_asc.data["TestCriticality"]["edges"]
    names_created_asc = [e["node"]["name"]["value"] for e in edges_created_asc]
    timestamps_created_asc = [e["node_metadata"]["created_at"] for e in edges_created_asc]

    # Main branch nodes should come first (created earlier), then branch nodes
    assert names_created_asc == ["main-first", "main-second", "branch-first", "branch-second"]
    assert timestamps_created_asc == sorted(timestamps_created_asc)

    # Test created_at DESC on user branch
    query_created_desc = """
    query {
        TestCriticality(order: {node_metadata: {created_at: DESC}}) {
            edges {
                node_metadata { created_at }
                node { name { value } }
            }
        }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=user_branch)
    result_created_desc = await graphql(
        schema=gql_params.schema,
        source=query_created_desc,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result_created_desc.errors is None
    assert result_created_desc.data
    edges_created_desc = result_created_desc.data["TestCriticality"]["edges"]
    names_created_desc = [e["node"]["name"]["value"] for e in edges_created_desc]
    timestamps_created_desc = [e["node_metadata"]["created_at"] for e in edges_created_desc]

    assert names_created_desc == ["branch-second", "branch-first", "main-second", "main-first"]
    assert timestamps_created_desc == sorted(timestamps_created_desc, reverse=True)

    # Update a main node on the user branch to make it the most recently updated
    main_obj1_on_branch = await NodeManager.get_one(db=db, id=main_obj1.id, branch=user_branch)
    main_obj1_on_branch.level.value = 100  # type: ignore[attr-defined]
    await main_obj1_on_branch.save(db=db)

    # Test updated_at DESC on user branch
    query_updated_desc = """
    query {
        TestCriticality(order: {node_metadata: {updated_at: DESC}}) {
            edges {
                node_metadata { updated_at }
                node { name { value } }
            }
        }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=user_branch)
    result_updated_desc = await graphql(
        schema=gql_params.schema,
        source=query_updated_desc,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result_updated_desc.errors is None
    assert result_updated_desc.data
    edges_updated_desc = result_updated_desc.data["TestCriticality"]["edges"]
    names_updated_desc = [e["node"]["name"]["value"] for e in edges_updated_desc]
    timestamps_updated_desc = [e["node_metadata"]["updated_at"] for e in edges_updated_desc]

    # main-first should be first (most recently updated on branch)
    assert names_updated_desc == ["main-first", "branch-second", "branch-first", "main-second"]
    assert timestamps_updated_desc == sorted(timestamps_updated_desc, reverse=True)

    # Test updated_at ASC on user branch
    query_updated_asc = """
    query {
        TestCriticality(order: {node_metadata: {updated_at: ASC}}) {
            edges {
                node_metadata { updated_at }
                node { name { value } }
            }
        }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=user_branch)
    result_updated_asc = await graphql(
        schema=gql_params.schema,
        source=query_updated_asc,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result_updated_asc.errors is None
    assert result_updated_asc.data
    edges_updated_asc = result_updated_asc.data["TestCriticality"]["edges"]
    names_updated_asc = [e["node"]["name"]["value"] for e in edges_updated_asc]
    timestamps_updated_asc = [e["node_metadata"]["updated_at"] for e in edges_updated_asc]

    # main-first should be last (most recently updated on branch)
    assert names_updated_asc == ["main-second", "branch-first", "branch-second", "main-first"]
    assert timestamps_updated_asc == sorted(timestamps_updated_asc)

    # Test pagination with created_at ordering - retrieve in batches of 2
    query_paginated = """
    query($offset: Int!, $limit: Int!) {
        TestCriticality(order: {node_metadata: {created_at: ASC}}, offset: $offset, limit: $limit) {
            edges {
                node_metadata { created_at }
                node { name { value } }
            }
        }
    }
    """
    paginated_names = []
    paginated_timestamps = []
    for offset in range(0, 4, 2):
        gql_params = await prepare_graphql_params(db=db, branch=user_branch)
        result_page = await graphql(
            schema=gql_params.schema,
            source=query_paginated,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"offset": offset, "limit": 2},
        )
        assert result_page.errors is None
        assert result_page.data
        edges_page = result_page.data["TestCriticality"]["edges"]
        paginated_names.extend([e["node"]["name"]["value"] for e in edges_page])
        paginated_timestamps.extend([e["node_metadata"]["created_at"] for e in edges_page])

    # Paginated results should match full created_at ASC ordering
    assert paginated_names == ["main-first", "main-second", "branch-first", "branch-second"]
    assert paginated_timestamps == sorted(paginated_timestamps)


# ============================================================================
# Metadata Filters Test Class
# ============================================================================


@dataclass
class MetadataFilterTestData:
    """Test data container for metadata filter tests."""

    # User IDs
    user_alice: str = "user-alice-uuid"
    user_bob: str = "user-bob-uuid"
    user_charlie: str = "user-charlie-uuid"
    user_diana: str = "user-diana-uuid"

    # Timestamps captured after node creation/updates
    ts_after_node1: Timestamp = field(default_factory=Timestamp)
    ts_after_node2: Timestamp = field(default_factory=Timestamp)
    ts_after_node4: Timestamp = field(default_factory=Timestamp)
    ts_after_node1_update: Timestamp = field(default_factory=Timestamp)

    # Branches
    user_branch: Branch | None = None


@pytest.fixture
async def metadata_filter_data(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> MetadataFilterTestData:
    """Set up test data for metadata filter tests.

    Creates:
    - 4 nodes on default branch with different creators
    - Updates to some nodes by different users
    - A user branch with 2 new nodes and 1 updated node
    """
    data = MetadataFilterTestData()

    # ========== DATA SETUP ON DEFAULT BRANCH ==========

    # Node 1: created by Alice on default branch
    node1 = await Node.init(db=db, schema=criticality_schema)
    await node1.new(db=db, name="node1", level=1)
    await node1.save(db=db, user_id=data.user_alice)
    data.ts_after_node1 = Timestamp()

    # Node 2: created by Bob on default branch
    node2 = await Node.init(db=db, schema=criticality_schema)
    await node2.new(db=db, name="node2", level=2)
    await node2.save(db=db, user_id=data.user_bob)
    data.ts_after_node2 = Timestamp()

    # Node 3: created by Alice on default branch
    node3 = await Node.init(db=db, schema=criticality_schema)
    await node3.new(db=db, name="node3", level=3)
    await node3.save(db=db, user_id=data.user_alice)

    # Node 4: created by Charlie on default branch
    node4 = await Node.init(db=db, schema=criticality_schema)
    await node4.new(db=db, name="node4", level=4)
    await node4.save(db=db, user_id=data.user_charlie)
    data.ts_after_node4 = Timestamp()

    # Update node1 (by Bob) on default branch
    node1_refreshed = await NodeManager.get_one(db=db, id=node1.id)
    node1_refreshed.level.value = 10  # type: ignore[attr-defined]
    await node1_refreshed.save(db=db, user_id=data.user_bob)
    data.ts_after_node1_update = Timestamp()

    # Update node3 (by Charlie) on default branch
    node3_refreshed = await NodeManager.get_one(db=db, id=node3.id)
    node3_refreshed.level.value = 30  # type: ignore[attr-defined]
    await node3_refreshed.save(db=db, user_id=data.user_charlie)

    # ========== CREATE USER BRANCH ==========
    data.user_branch = await create_branch(branch_name="test-metadata-filters-branch", db=db)

    # ========== DATA SETUP ON USER BRANCH ==========

    # Node 5: created by Diana on user branch
    node5 = await Node.init(db=db, schema=criticality_schema, branch=data.user_branch)
    await node5.new(db=db, name="branch-node5", level=5)
    await node5.save(db=db, user_id=data.user_diana)

    # Node 6: created by Alice on user branch
    node6 = await Node.init(db=db, schema=criticality_schema, branch=data.user_branch)
    await node6.new(db=db, name="branch-node6", level=6)
    await node6.save(db=db, user_id=data.user_alice)

    # Update node2 (by Diana) on user branch - modifies a main branch node on the branch
    node2_branch = await NodeManager.get_one(db=db, id=node2.id, branch=data.user_branch)
    node2_branch.level.value = 20  # type: ignore[attr-defined]
    await node2_branch.save(db=db, user_id=data.user_diana)

    return data


class TestMetadataFilters:
    """Test class for metadata filtering functionality."""

    async def _run_query(
        self, db: InfrahubDatabase, query_str: str, branch: Branch, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query and return the data."""
        gql_params = await prepare_graphql_params(db=db, branch=branch)
        result = await graphql(
            schema=gql_params.schema,
            source=query_str,
            context_value=gql_params.context,
            root_value=None,
            variable_values=variables or {},
        )
        assert result.errors is None, f"GraphQL errors: {result.errors}"
        assert result.data
        return result.data

    def _get_names(self, data: dict[str, Any], query_name: str = "TestCriticality") -> set[str]:
        """Extract node names from query result."""
        return {e["node"]["name"]["value"] for e in data[query_name]["edges"]}

    # ========== DateTime Filter Tests on Default Branch ==========

    async def test_created_at_after_on_default_branch(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test created_at__after filter on default branch."""
        query = """
        query($cutoff: DateTime!) {
            TestCriticality(node_metadata__created_at__after: $cutoff) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes created after node1 should be node2, node3, node4
        data = await self._run_query(
            db, query, default_branch, {"cutoff": metadata_filter_data.ts_after_node1.to_datetime()}
        )
        assert data["TestCriticality"]["count"] == 3
        assert self._get_names(data) == {"node2", "node3", "node4"}

    async def test_created_at_before_on_default_branch(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test created_at__before filter on default branch."""
        query = """
        query($cutoff: DateTime!) {
            TestCriticality(node_metadata__created_at__before: $cutoff) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes created before node3 should be node1, node2
        data = await self._run_query(
            db, query, default_branch, {"cutoff": metadata_filter_data.ts_after_node2.to_datetime()}
        )
        assert data["TestCriticality"]["count"] == 2
        assert self._get_names(data) == {"node1", "node2"}

    async def test_updated_at_after_on_default_branch(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test updated_at__after filter on default branch."""
        query = """
        query($cutoff: DateTime!) {
            TestCriticality(node_metadata__updated_at__after: $cutoff) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes updated after all initial creates (only node1 and node3 were updated later)
        data = await self._run_query(
            db, query, default_branch, {"cutoff": metadata_filter_data.ts_after_node4.to_datetime()}
        )
        assert data["TestCriticality"]["count"] == 2
        assert self._get_names(data) == {"node1", "node3"}

    async def test_updated_at_before_on_default_branch(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test updated_at__before filter on default branch."""
        query = """
        query($cutoff: DateTime!) {
            TestCriticality(node_metadata__updated_at__before: $cutoff) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes with updated_at before ts_after_node1_update:
        # - node1 (just updated), node2 (never updated), node4 (never updated)
        # - node3 was updated AFTER ts_after_node1_update so it's excluded
        data = await self._run_query(
            db, query, default_branch, {"cutoff": metadata_filter_data.ts_after_node1_update.to_datetime()}
        )
        assert data["TestCriticality"]["count"] == 3
        assert self._get_names(data) == {"node1", "node2", "node4"}

    # ========== ID-based Filter Tests on Default Branch ==========

    async def test_created_by_id_on_default_branch(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test created_by__id filter on default branch."""
        query = """
        query($userId: ID!) {
            TestCriticality(node_metadata__created_by__id: $userId) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes created by Alice should be node1, node3
        data = await self._run_query(db, query, default_branch, {"userId": metadata_filter_data.user_alice})
        assert data["TestCriticality"]["count"] == 2
        assert self._get_names(data) == {"node1", "node3"}

        # Nodes created by Bob should be node2
        data = await self._run_query(db, query, default_branch, {"userId": metadata_filter_data.user_bob})
        assert data["TestCriticality"]["count"] == 1
        assert self._get_names(data) == {"node2"}

    async def test_created_by_ids_on_default_branch(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test created_by__ids filter on default branch."""
        query = """
        query($userIds: [ID]!) {
            TestCriticality(node_metadata__created_by__ids: $userIds) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes created by Alice or Bob should be node1, node2, node3
        data = await self._run_query(
            db, query, default_branch, {"userIds": [metadata_filter_data.user_alice, metadata_filter_data.user_bob]}
        )
        assert data["TestCriticality"]["count"] == 3
        assert self._get_names(data) == {"node1", "node2", "node3"}

    async def test_updated_by_id_on_default_branch(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test updated_by__id filter on default branch."""
        query = """
        query($userId: ID!) {
            TestCriticality(node_metadata__updated_by__id: $userId) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes last updated by Bob should be node1 (updated), node2 (created by Bob)
        data = await self._run_query(db, query, default_branch, {"userId": metadata_filter_data.user_bob})
        assert data["TestCriticality"]["count"] == 2
        assert self._get_names(data) == {"node1", "node2"}

        # Nodes last updated by Charlie should be node3 (updated), node4 (created by Charlie)
        data = await self._run_query(db, query, default_branch, {"userId": metadata_filter_data.user_charlie})
        assert data["TestCriticality"]["count"] == 2
        assert self._get_names(data) == {"node3", "node4"}

    async def test_updated_by_ids_on_default_branch(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test updated_by__ids filter on default branch."""
        query = """
        query($userIds: [ID]!) {
            TestCriticality(node_metadata__updated_by__ids: $userIds) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes last updated by Bob or Charlie should be all 4 nodes
        data = await self._run_query(
            db, query, default_branch, {"userIds": [metadata_filter_data.user_bob, metadata_filter_data.user_charlie]}
        )
        assert data["TestCriticality"]["count"] == 4
        assert self._get_names(data) == {"node1", "node2", "node3", "node4"}

    # ========== ID-based Filter Tests on User Branch ==========

    async def test_created_by_id_on_user_branch(
        self, db: InfrahubDatabase, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test created_by__id filter on user branch."""
        assert metadata_filter_data.user_branch is not None
        query = """
        query($userId: ID!) {
            TestCriticality(node_metadata__created_by__id: $userId) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes created by Alice (node1, node3 from main + branch-node6 from branch)
        data = await self._run_query(
            db, query, metadata_filter_data.user_branch, {"userId": metadata_filter_data.user_alice}
        )
        assert data["TestCriticality"]["count"] == 3
        assert self._get_names(data) == {"node1", "node3", "branch-node6"}

        # Nodes created by Diana (only branch-node5)
        data = await self._run_query(
            db, query, metadata_filter_data.user_branch, {"userId": metadata_filter_data.user_diana}
        )
        assert data["TestCriticality"]["count"] == 1
        assert self._get_names(data) == {"branch-node5"}

    async def test_updated_by_id_on_user_branch(
        self, db: InfrahubDatabase, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test updated_by__id filter on user branch."""
        assert metadata_filter_data.user_branch is not None
        query = """
        query($userId: ID!) {
            TestCriticality(node_metadata__updated_by__id: $userId) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes last updated by Diana: node2 (updated on branch), branch-node5 (created by Diana)
        data = await self._run_query(
            db, query, metadata_filter_data.user_branch, {"userId": metadata_filter_data.user_diana}
        )
        assert data["TestCriticality"]["count"] == 2
        assert self._get_names(data) == {"node2", "branch-node5"}

        # Nodes last updated by Bob on branch: node1 (from main, updated by Bob on main)
        data = await self._run_query(
            db, query, metadata_filter_data.user_branch, {"userId": metadata_filter_data.user_bob}
        )
        assert data["TestCriticality"]["count"] == 1
        assert self._get_names(data) == {"node1"}

    async def test_created_by_ids_on_user_branch(
        self, db: InfrahubDatabase, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test created_by__ids filter on user branch."""
        assert metadata_filter_data.user_branch is not None
        query = """
        query($userIds: [ID]!) {
            TestCriticality(node_metadata__created_by__ids: $userIds) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes created by Alice or Diana
        data = await self._run_query(
            db,
            query,
            metadata_filter_data.user_branch,
            {"userIds": [metadata_filter_data.user_alice, metadata_filter_data.user_diana]},
        )
        assert data["TestCriticality"]["count"] == 4
        assert self._get_names(data) == {"node1", "node3", "branch-node5", "branch-node6"}

    # ========== Combined ID-based Filter Tests ==========

    async def test_combined_created_by_ids_and_updated_by_id_on_default_branch(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test combining created_by__ids and updated_by__id on default branch."""
        query = """
        query($createdByIds: [ID]!, $updatedById: ID!) {
            TestCriticality(node_metadata__created_by__ids: $createdByIds, node_metadata__updated_by__id: $updatedById) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes created by Alice or Bob, last updated by Bob should be node1, node2
        data = await self._run_query(
            db,
            query,
            default_branch,
            {
                "createdByIds": [metadata_filter_data.user_alice, metadata_filter_data.user_bob],
                "updatedById": metadata_filter_data.user_bob,
            },
        )
        assert data["TestCriticality"]["count"] == 2
        assert self._get_names(data) == {"node1", "node2"}

    async def test_combined_id_filters_on_user_branch(
        self, db: InfrahubDatabase, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test combining created_by__ids and updated_by__id on user branch."""
        assert metadata_filter_data.user_branch is not None
        query = """
        query($createdByIds: [ID]!, $updatedById: ID!) {
            TestCriticality(node_metadata__created_by__ids: $createdByIds, node_metadata__updated_by__id: $updatedById) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes created by Alice or Diana, last updated by Bob should be node1 only
        data = await self._run_query(
            db,
            query,
            metadata_filter_data.user_branch,
            {
                "createdByIds": [metadata_filter_data.user_alice, metadata_filter_data.user_diana],
                "updatedById": metadata_filter_data.user_bob,
            },
        )
        assert data["TestCriticality"]["count"] == 1
        assert self._get_names(data) == {"node1"}

        # Nodes created by Alice or Diana, last updated by Diana should be branch-node5 only
        # (branch-node6 was created by Alice but updated_by = Alice since never explicitly updated)
        data = await self._run_query(
            db,
            query,
            metadata_filter_data.user_branch,
            {
                "createdByIds": [metadata_filter_data.user_alice, metadata_filter_data.user_diana],
                "updatedById": metadata_filter_data.user_diana,
            },
        )
        assert data["TestCriticality"]["count"] == 1
        assert self._get_names(data) == {"branch-node5"}

    # ========== DateTime Filter Tests on User Branch ==========

    async def test_created_at_after_on_user_branch(
        self, db: InfrahubDatabase, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test created_at__after filter on user branch."""
        assert metadata_filter_data.user_branch is not None
        query = """
        query($cutoff: DateTime!) {
            TestCriticality(node_metadata__created_at__after: $cutoff) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Should return branch-node5, branch-node6 (created after node4)
        data = await self._run_query(
            db, query, metadata_filter_data.user_branch, {"cutoff": metadata_filter_data.ts_after_node4.to_datetime()}
        )
        assert data["TestCriticality"]["count"] == 2
        assert self._get_names(data) == {"branch-node5", "branch-node6"}

    async def test_updated_at_after_on_user_branch(
        self, db: InfrahubDatabase, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test updated_at__after filter on user branch."""
        assert metadata_filter_data.user_branch is not None
        query = """
        query($cutoff: DateTime!) {
            TestCriticality(node_metadata__updated_at__after: $cutoff) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Should return nodes updated after node1_update on default branch
        data = await self._run_query(
            db,
            query,
            metadata_filter_data.user_branch,
            {"cutoff": metadata_filter_data.ts_after_node1_update.to_datetime()},
        )
        # node3 (updated on main), branch-node5, branch-node6, node2 (updated on branch)
        assert data["TestCriticality"]["count"] >= 1
        assert self._get_names(data) == {"node3", "branch-node5", "branch-node6", "node2"}

    async def test_combined_created_by_and_created_at_after(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test combining created_by__id with created_at__after"""
        query = """
        query($userId: ID!, $cutoff: DateTime!) {
            TestCriticality(node_metadata__created_by__id: $userId, node_metadata__created_at__after: $cutoff) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes created by Alice after node1 should be node3
        data = await self._run_query(
            db,
            query,
            default_branch,
            {"userId": metadata_filter_data.user_alice, "cutoff": metadata_filter_data.ts_after_node1.to_datetime()},
        )
        assert data["TestCriticality"]["count"] == 1
        assert self._get_names(data) == {"node3"}

    async def test_combined_updated_by_and_updated_at_after(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test combining updated_by__id with updated_at__after"""
        query = """
        query($userId: ID!, $cutoff: DateTime!) {
            TestCriticality(node_metadata__updated_by__id: $userId, node_metadata__updated_at__after: $cutoff) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes updated by Charlie after all initial creates should be node3
        data = await self._run_query(
            db,
            query,
            default_branch,
            {"userId": metadata_filter_data.user_charlie, "cutoff": metadata_filter_data.ts_after_node4.to_datetime()},
        )
        assert data["TestCriticality"]["count"] == 1
        assert self._get_names(data) == {"node3"}

    async def test_created_at_range(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test created_at__after combined with created_at__before (date range)"""
        query = """
        query($after: DateTime!, $before: DateTime!) {
            TestCriticality(node_metadata__created_at__after: $after, node_metadata__created_at__before: $before) {
                count
                edges { node { name { value } } }
            }
        }
        """
        # Nodes created between node1 and node4 should be node2, node3, node4
        data = await self._run_query(
            db,
            query,
            default_branch,
            {
                "after": metadata_filter_data.ts_after_node1.to_datetime(),
                "before": metadata_filter_data.ts_after_node4.to_datetime(),
            },
        )
        assert data["TestCriticality"]["count"] == 3
        assert self._get_names(data) == {"node2", "node3", "node4"}

    # ========== Combined Filter + Order Tests (Same Field) ==========

    async def test_filter_and_order_by_created_at(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by created_at__after and ordering by created_at ASC."""
        query = """
        query($cutoff: DateTime!) {
            TestCriticality(
                node_metadata__created_at__after: $cutoff,
                order: {node_metadata: {created_at: ASC}}
            ) {
                count
                edges {
                    node_metadata { created_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes created after node1, Order: by created_at ASC
        data = await self._run_query(
            db, query, default_branch, {"cutoff": metadata_filter_data.ts_after_node1.to_datetime()}
        )
        assert data["TestCriticality"]["count"] == 3
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["created_at"] for e in data["TestCriticality"]["edges"]]
        # Should be node2, node3, node4 in creation order
        assert names == ["node2", "node3", "node4"]
        assert timestamps == sorted(timestamps)

    async def test_filter_and_order_by_created_at_desc(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by created_at__before and ordering by created_at DESC."""
        query = """
        query($cutoff: DateTime!) {
            TestCriticality(
                node_metadata__created_at__before: $cutoff,
                order: {node_metadata: {created_at: DESC}}
            ) {
                count
                edges {
                    node_metadata { created_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes created before node2, Order: by created_at DESC
        data = await self._run_query(
            db, query, default_branch, {"cutoff": metadata_filter_data.ts_after_node2.to_datetime()}
        )
        assert data["TestCriticality"]["count"] == 2
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["created_at"] for e in data["TestCriticality"]["edges"]]
        # Should be node2, node1 in reverse creation order
        assert names == ["node2", "node1"]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_filter_and_order_by_updated_at(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by updated_at__after and ordering by updated_at DESC."""
        query = """
        query($cutoff: DateTime!) {
            TestCriticality(
                node_metadata__updated_at__after: $cutoff,
                order: {node_metadata: {updated_at: DESC}}
            ) {
                count
                edges {
                    node_metadata { updated_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes updated after node4 creation, Order: by updated_at DESC
        # node1 and node3 were updated after node4 was created
        data = await self._run_query(
            db, query, default_branch, {"cutoff": metadata_filter_data.ts_after_node4.to_datetime()}
        )
        assert data["TestCriticality"]["count"] == 2
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["updated_at"] for e in data["TestCriticality"]["edges"]]
        # node3 was updated last, so it should be first in DESC order
        assert names == ["node3", "node1"]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_filter_by_created_by_and_order_by_created_at(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by created_by__id and ordering by created_at ASC."""
        query = """
        query($userId: ID!) {
            TestCriticality(
                node_metadata__created_by__id: $userId,
                order: {node_metadata: {created_at: ASC}}
            ) {
                count
                edges {
                    node_metadata { created_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes created by Alice, Order: by created_at ASC
        data = await self._run_query(db, query, default_branch, {"userId": metadata_filter_data.user_alice})
        assert data["TestCriticality"]["count"] == 2
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["created_at"] for e in data["TestCriticality"]["edges"]]
        # node1 was created before node3
        assert names == ["node1", "node3"]
        assert timestamps == sorted(timestamps)

    async def test_filter_by_updated_by_and_order_by_updated_at(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by updated_by__id and ordering by updated_at DESC."""
        query = """
        query($userId: ID!) {
            TestCriticality(
                node_metadata__updated_by__id: $userId,
                order: {node_metadata: {updated_at: DESC}}
            ) {
                count
                edges {
                    node_metadata { updated_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes last updated by Bob (node1, node2), Order: by updated_at DESC
        data = await self._run_query(db, query, default_branch, {"userId": metadata_filter_data.user_bob})
        assert data["TestCriticality"]["count"] == 2
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["updated_at"] for e in data["TestCriticality"]["edges"]]
        # node1 was updated after node2 was created
        assert names == ["node1", "node2"]
        assert timestamps == sorted(timestamps, reverse=True)

    # ========== Combined Filter + Order Tests (Different Fields) ==========

    async def test_filter_by_created_by_order_by_updated_at(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by created_by__id and ordering by updated_at DESC."""
        query = """
        query($userId: ID!) {
            TestCriticality(
                node_metadata__created_by__id: $userId,
                order: {node_metadata: {updated_at: DESC}}
            ) {
                count
                edges {
                    node_metadata { updated_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes created by Alice (node1, node3), Order: by updated_at DESC
        # node3 was updated more recently than node1
        data = await self._run_query(db, query, default_branch, {"userId": metadata_filter_data.user_alice})
        assert data["TestCriticality"]["count"] == 2
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["updated_at"] for e in data["TestCriticality"]["edges"]]
        # node3 was updated last (by Charlie), node1 was updated before that (by Bob)
        assert names == ["node3", "node1"]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_filter_by_updated_by_order_by_created_at(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by updated_by__id and ordering by created_at ASC."""
        query = """
        query($userId: ID!) {
            TestCriticality(
                node_metadata__updated_by__id: $userId,
                order: {node_metadata: {created_at: ASC}}
            ) {
                count
                edges {
                    node_metadata { created_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes last updated by Charlie (node3, node4), Order: by created_at ASC
        data = await self._run_query(db, query, default_branch, {"userId": metadata_filter_data.user_charlie})
        assert data["TestCriticality"]["count"] == 2
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["created_at"] for e in data["TestCriticality"]["edges"]]
        # node3 was created before node4
        assert names == ["node3", "node4"]
        assert timestamps == sorted(timestamps)

    async def test_filter_by_created_by_ids_order_by_updated_at(
        self, db: InfrahubDatabase, default_branch: Branch, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by created_by__ids and ordering by updated_at ASC."""
        query = """
        query($userIds: [ID]!) {
            TestCriticality(
                node_metadata__created_by__ids: $userIds,
                order: {node_metadata: {updated_at: ASC}}
            ) {
                count
                edges {
                    node_metadata { updated_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes created by Alice or Bob (node1, node2, node3), Order: by updated_at ASC
        data = await self._run_query(
            db, query, default_branch, {"userIds": [metadata_filter_data.user_alice, metadata_filter_data.user_bob]}
        )
        assert data["TestCriticality"]["count"] == 3
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["updated_at"] for e in data["TestCriticality"]["edges"]]
        # node2 was never explicitly updated, node1 was updated, then node3 was updated last
        assert names == ["node2", "node1", "node3"]
        assert timestamps == sorted(timestamps)

    async def test_filter_by_created_at_order_by_updated_at_on_user_branch(
        self, db: InfrahubDatabase, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by created_at__after and ordering by updated_at DESC on user branch."""
        assert metadata_filter_data.user_branch is not None
        query = """
        query($cutoff: DateTime!) {
            TestCriticality(
                node_metadata__created_at__after: $cutoff,
                order: {node_metadata: {updated_at: DESC}}
            ) {
                count
                edges {
                    node_metadata { updated_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes created after node4 (branch-node5, branch-node6), Order: by updated_at DESC
        data = await self._run_query(
            db, query, metadata_filter_data.user_branch, {"cutoff": metadata_filter_data.ts_after_node4.to_datetime()}
        )
        assert data["TestCriticality"]["count"] == 2
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["updated_at"] for e in data["TestCriticality"]["edges"]]
        # branch-node6 was created after branch-node5, so it should be first in DESC order
        assert names == ["branch-node6", "branch-node5"]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_filter_by_created_by_order_by_created_at_on_user_branch(
        self, db: InfrahubDatabase, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by created_by__id and ordering by created_at ASC on user branch."""
        assert metadata_filter_data.user_branch is not None
        query = """
        query($userId: ID!) {
            TestCriticality(
                node_metadata__created_by__id: $userId,
                order: {node_metadata: {created_at: ASC}}
            ) {
                count
                edges {
                    node_metadata { created_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes created by Alice on user branch (node1, node3 from main + branch-node6)
        # Order: by created_at ASC
        data = await self._run_query(
            db, query, metadata_filter_data.user_branch, {"userId": metadata_filter_data.user_alice}
        )
        assert data["TestCriticality"]["count"] == 3
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["created_at"] for e in data["TestCriticality"]["edges"]]
        # node1 was created first, then node3, then branch-node6 (on the branch)
        assert names == ["node1", "node3", "branch-node6"]
        assert timestamps == sorted(timestamps)

    async def test_filter_by_updated_by_order_by_updated_at_on_user_branch(
        self, db: InfrahubDatabase, metadata_filter_data: MetadataFilterTestData
    ) -> None:
        """Test filtering by updated_by__id and ordering by updated_at DESC on user branch."""
        assert metadata_filter_data.user_branch is not None
        query = """
        query($userId: ID!) {
            TestCriticality(
                node_metadata__updated_by__id: $userId,
                order: {node_metadata: {updated_at: DESC}}
            ) {
                count
                edges {
                    node_metadata { updated_at }
                    node { name { value } }
                }
            }
        }
        """
        # Filter: nodes last updated by Diana on branch (node2, branch-node5), Order: updated_at DESC
        data = await self._run_query(
            db, query, metadata_filter_data.user_branch, {"userId": metadata_filter_data.user_diana}
        )
        assert data["TestCriticality"]["count"] == 2
        names = [e["node"]["name"]["value"] for e in data["TestCriticality"]["edges"]]
        timestamps = [e["node_metadata"]["updated_at"] for e in data["TestCriticality"]["edges"]]
        # node2 was updated on the branch after branch-node5 was created
        assert names == ["node2", "branch-node5"]
        assert timestamps == sorted(timestamps, reverse=True)
