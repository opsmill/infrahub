"""Test for merging relationships to AGNOSTIC peer nodes (like CoreIPAddressPool).

This test reproduces the bug reported in GitHub issue #7896 where relationships
to CoreIPAddressPool are not properly merged because AGNOSTIC nodes have their
IS_PART_OF edge on the global branch, not on the source/target branches.
"""

from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.test_app import TestInfrahubApp


class TestDiffMergeAgnosticPeer(TestInfrahubApp):
    """Test merging relationships to AGNOSTIC nodes (e.g., CoreIPAddressPool)."""

    @pytest.fixture(scope="class")
    async def ipam_schema(self) -> SchemaRoot:
        """Schema for IPAM nodes."""
        SCHEMA: dict[str, Any] = {
            "nodes": [
                {
                    "name": "IPPrefix",
                    "namespace": "Ipam",
                    "default_filter": "prefix__value",
                    "order_by": ["prefix__value"],
                    "display_labels": ["prefix__value"],
                    "branch": BranchSupportType.AWARE.value,
                    "inherit_from": [InfrahubKind.IPPREFIX, InfrahubKind.WEIGHTED_POOL_RESOURCE],
                },
                {
                    "name": "IPAddress",
                    "namespace": "Ipam",
                    "default_filter": "address__value",
                    "order_by": ["address__value"],
                    "display_labels": ["address__value"],
                    "branch": BranchSupportType.AWARE.value,
                    "inherit_from": [InfrahubKind.IPADDRESS],
                },
            ],
        }
        return SchemaRoot(**SCHEMA)

    @pytest.fixture(scope="class")
    async def pod_schema(self) -> SchemaRoot:
        """Schema with a relationship to CoreIPAddressPool (AGNOSTIC node)."""
        SCHEMA: dict[str, Any] = {
            "nodes": [
                {
                    "name": "Pod",
                    "namespace": "Networking",
                    "human_friendly_id": ["name__value"],
                    "uniqueness_constraints": [["name__value"]],
                    "attributes": [
                        {"name": "name", "kind": "Text", "optional": False},
                    ],
                    "relationships": [
                        {
                            "name": "loopback_pool",
                            "peer": InfrahubKind.IPADDRESSPOOL,
                            "kind": "Attribute",
                            "optional": True,
                            "cardinality": "one",
                        },
                    ],
                },
            ],
        }
        return SchemaRoot(**SCHEMA)

    @pytest.fixture(scope="class")
    async def register_ipam_schema(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        ipam_schema: SchemaRoot,
    ) -> SchemaBranch:
        schema_branch = registry.schema.register_schema(schema=ipam_schema, branch=default_branch.name)
        default_branch.update_schema_hash()
        await default_branch.save(db=db)
        return schema_branch

    @pytest.fixture(scope="class")
    async def register_pod_schema(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_ipam_schema: SchemaBranch,
        pod_schema: SchemaRoot,
    ) -> SchemaBranch:
        schema_branch = registry.schema.register_schema(schema=pod_schema, branch=default_branch.name)
        default_branch.update_schema_hash()
        await default_branch.save(db=db)
        return schema_branch

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_pod_schema: SchemaBranch,
    ) -> dict[str, Node]:
        """Create initial dataset: IP namespace, prefix, and IP address pool."""
        # Create IP namespace
        ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns.new(db=db, name="default")
        await ns.save(db=db)

        # Create IP prefix
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
        prefix = await Node.init(db=db, schema=prefix_schema)
        await prefix.new(db=db, prefix="10.0.0.0/24", ip_namespace=ns)
        await prefix.save(db=db)

        # Create IP address pool (AGNOSTIC node)
        pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)
        pool = await CoreIPAddressPool.init(schema=pool_schema, db=db)
        await pool.new(
            db=db,
            name="loopback-pool",
            resources=[prefix],
            ip_namespace=ns,
            default_address_type="IpamIPAddress",
        )
        await pool.save(db=db)

        return {
            "ns": ns,
            "prefix": prefix,
            "pool": pool,
        }

    @pytest.fixture(scope="class")
    async def diff_branch(
        self,
        db: InfrahubDatabase,
        initial_dataset: dict[str, Node],
    ) -> Branch:
        """Create a branch for making changes."""
        return await create_branch(db=db, branch_name="test-pool-relationship")

    @pytest.fixture(scope="class")
    async def diff_repository(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

    @pytest.fixture(scope="class")
    async def diff_coordinator(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> DiffCoordinator:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffCoordinator, db=db, branch=default_branch)

    async def _get_diff_merger(self, db: InfrahubDatabase, diff_branch: Branch) -> DiffMerger:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffMerger, db=db, branch=diff_branch)

    async def test_merge_relationship_to_agnostic_peer(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_branch: Branch,
        initial_dataset: dict[str, Node],
        diff_coordinator: DiffCoordinator,
        diff_repository: DiffRepository,
    ) -> None:
        """Test that relationships to AGNOSTIC nodes (CoreIPAddressPool) are properly merged.

        This test reproduces the bug from GitHub issue #7896 where:
        1. Create a Pod on a branch with a relationship to CoreIPAddressPool
        2. Merge the branch
        3. The relationship to CoreIPAddressPool should exist on the main branch

        The root cause was that DiffMergeQuery was filtering peer nodes by
        IS_PART_OF.branch IN [$source_branch, $target_branch], but AGNOSTIC nodes
        like CoreIPAddressPool have their IS_PART_OF on the global branch.
        """
        pool = initial_dataset["pool"]

        # Create a Pod on the branch with a relationship to the CoreIPAddressPool
        pod_schema = registry.schema.get_node_schema(name="NetworkingPod", branch=diff_branch)
        pod = await Node.init(db=db, schema=pod_schema, branch=diff_branch)
        await pod.new(db=db, name="pod-1", loopback_pool=pool)
        await pod.save(db=db)

        # Calculate and save the diff
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch,
            diff_branch=diff_branch,
        )

        # Verify there are no conflicts
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name,
            diff_id=enriched_diff_metadata.uuid,
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 0, f"Unexpected conflicts: {conflicts_map}"

        # Merge the branch
        right_now = Timestamp()
        diff_merger = await self._get_diff_merger(db=db, diff_branch=diff_branch)
        await diff_merger.merge_graph(at=right_now)

        # Verify the Pod exists on main branch
        pod_main = await NodeManager.get_one(db=db, branch=default_branch, id=pod.get_id())
        assert pod_main is not None, "Pod should exist on main branch after merge"

        # Verify the relationship to CoreIPAddressPool exists on main branch
        # This is the actual bug - the relationship was not being merged
        loopback_pool_peer = await pod_main.loopback_pool.get_peer(db=db)
        assert loopback_pool_peer is not None, (
            "Relationship to CoreIPAddressPool should exist on main branch after merge. "
            "This is the bug from GitHub issue #7896."
        )
        assert loopback_pool_peer.get_id() == pool.get_id(), (
            f"Expected loopback_pool to be {pool.get_id()}, got {loopback_pool_peer.get_id()}"
        )
