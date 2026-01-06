import pytest

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.migrations.graph.m033_deduplicate_relationship_vertices import Migration033
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase


class TestMigration033:
    @pytest.fixture(scope="class")
    async def legal_relationship_dicts(self) -> list[dict[str, str | int]]:
        return [
            # node on main, rel on main created after node
            {
                "uuid": "legal_main_main",
                "source_uuid": "main_node_zero",
                "dest_uuid": "main_node",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-02T00:00:01Z",
            },
            # node on main, rel on branch (created before node) created after node
            {
                "uuid": "legal_main_branch",
                "source_uuid": "main_node_zero",
                "dest_uuid": "branch_a_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-03T00:00:02Z",
            },
            # node on main, rel on global created after node
            {
                "uuid": "legal_main_global",
                "source_uuid": "main_node_zero",
                "dest_uuid": "global_node",
                "branch": GLOBAL_BRANCH_NAME,
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:01Z",
            },
            # node on global, rel on main created after node
            {
                "uuid": "legal_global_main",
                "source_uuid": "global_node",
                "dest_uuid": "main_node",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-02T00:00:02Z",
            },
            # node on global, rel on branch created after node
            {
                "uuid": "legal_global_branch",
                "source_uuid": "global_node",
                "dest_uuid": "branch_a_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-03T00:00:02Z",
            },
            # node on global, rel on global created after node
            {
                "uuid": "legal_global_global",
                "source_uuid": "global_node",
                "dest_uuid": "global_node_zero",
                "branch": GLOBAL_BRANCH_NAME,
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:03Z",
            },
            # node on branch, rel on same branch created after node
            {
                "uuid": "legal_branch_branch",
                "source_uuid": "branch_a_node_one",
                "dest_uuid": "branch_a_node_two",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-04T00:00:02Z",
            },
            # node on branch deleted, rel on branch during node active time
            {
                "uuid": "legal_branch_branch_deleted",
                "source_uuid": "branch_a_node_deleted",
                "dest_uuid": "branch_a_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-03T02:00:01Z",
            },
        ]

    @pytest.fixture(scope="class")
    async def illegal_relationship_dicts(self) -> list[dict[str, str | int]]:
        return [
            # node on main, rel on global created before node
            {
                "uuid": "illegal_main_global",
                "source_uuid": "main_node",
                "dest_uuid": "global_node",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2024-12-31T00:00:01Z",
            },
            # node on main, rel on main created before node
            {
                "uuid": "illegal_main_main",
                "source_uuid": "main_node_zero",
                "dest_uuid": "main_node",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2024-12-31T00:00:0Z",
            },
            # node on main, rel on branch (created before node) created before node
            {
                "uuid": "illegal_main_branch_one",
                "source_uuid": "main_node_last",
                "dest_uuid": "branch_a_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2024-01-31T00:00:00Z",
            },
            # node on main, rel on branch (created before node) created after node
            {
                "uuid": "illegal_main_branch_two",
                "source_uuid": "main_node_last",
                "dest_uuid": "branch_a_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-31T00:00:00Z",
            },
            # node on global, rel on global created before node
            {
                "uuid": "illegal_global_global",
                "source_uuid": "global_node",
                "dest_uuid": "global_node_zero",
                "branch": GLOBAL_BRANCH_NAME,
                "branch_level": 1,
                "from_time": "2024-12-31T00:00:01Z",
            },
            # node on global, rel on main created before node
            {
                "uuid": "illegal_global_main",
                "source_uuid": "global_node",
                "dest_uuid": "main_node",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2024-12-31T00:00:0Z",
            },
            # node on global, rel on branch (created before node) created before node
            {
                "uuid": "illegal_global_branch_one",
                "source_uuid": "global_node_last",
                "dest_uuid": "branch_a_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2024-01-31T00:00:00Z",
            },
            # node on global, rel on branch (created before node) created after node
            {
                "uuid": "illegal_global_branch_two",
                "source_uuid": "global_node_last",
                "dest_uuid": "branch_a_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-31T00:00:00Z",
            },
            # node on branch, rel on different branch created before node
            {
                "uuid": "illegal_branch_branch_one",
                "source_uuid": "branch_a_node_one",
                "dest_uuid": "branch_b_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2024-01-31T00:00:00Z",
            },
            # node on branch, rel on different branch created after node
            {
                "uuid": "illegal_branch_branch_two",
                "source_uuid": "branch_a_node_one",
                "dest_uuid": "branch_b_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-31T00:00:00Z",
            },
            # node on branch, rel on same branch created before node
            {
                "uuid": "illegal_branch_branch_three",
                "source_uuid": "branch_a_node_one",
                "dest_uuid": "branch_a_node_two",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2024-01-31T00:00:00Z",
            },
            # node on branch deleted, rel on same branch after node deleted
            {
                "uuid": "illegal_branch_branch_deleted",
                "source_uuid": "branch_a_node_deleted",
                "dest_uuid": "branch_a_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-02-03T02:00:03Z",
            },
        ]

    @pytest.fixture(scope="class")
    async def load_bad_data(
        self,
        db: InfrahubDatabase,
        legal_relationship_dicts: list[dict[str, str | int]],
        illegal_relationship_dicts: list[dict[str, str | int]],
    ) -> None:
        await delete_all_nodes(db=db)
        root_and_branch_query = """
MERGE (root:Root {default_branch: "main"})
MERGE (main:Branch {name: "main", branched_from: "2023-01-01T00:00:00"})
MERGE (global:Branch {name: "-global-", branched_from: "2023-01-02T00:00:00"})
MERGE (branch_a:Branch {name: "branch_a", branched_from: "2025-01-03T00:00:00"})
MERGE (branch_b:Branch {name: "branch_b", branched_from: "2025-01-04T00:00:00"})
        """
        await db.execute_query(query=root_and_branch_query)

        nodes = [
            # main node zero - 2024-01-01
            {
                "labels": ["MainNode"],
                "uuid": "main_node_zero",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2024-01-01T00:00:00Z",
            },
            # global node zero - 2024-01-02
            {
                "labels": ["GlobalNode"],
                "uuid": "global_node_zero",
                "branch": GLOBAL_BRANCH_NAME,
                "branch_level": 1,
                "from_time": "2024-01-02T00:00:00Z",
            },
            # main node - 2025-01-02
            {
                "labels": ["MainNode"],
                "uuid": "main_node",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-02T00:00:00Z",
            },
            # main node last - 2026-01-01
            {
                "labels": ["MainNode"],
                "uuid": "main_node_last",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2026-01-01T00:00:00Z",
            },
            # global node - 2025-01-01
            {
                "labels": ["GlobalNode"],
                "uuid": "global_node",
                "branch": GLOBAL_BRANCH_NAME,
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:00Z",
            },
            # global node last - 2026-01-02
            {
                "labels": ["GlobalNode"],
                "uuid": "global_node_last",
                "branch": GLOBAL_BRANCH_NAME,
                "branch_level": 1,
                "from_time": "2026-01-02T00:00:00Z",
            },
            # branch A node one - 2025-01-03
            {
                "labels": ["BranchNode"],
                "uuid": "branch_a_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-03T00:00:01Z",
            },
            # branch A node two - 2025-01-03
            {
                "labels": ["BranchNode"],
                "uuid": "branch_a_node_two",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-03T01:00:01Z",
            },
            # branch A node deleted - 2025-01-03
            {
                "labels": ["BranchNode"],
                "uuid": "branch_a_node_deleted",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-03T02:00:01Z",
                "to_time": "2025-02-03T02:00:02Z",
            },
            # branch B node one - 2025-01-04
            {
                "labels": ["BranchNode"],
                "uuid": "branch_b_node_one",
                "branch": "branch_b",
                "branch_level": 2,
                "from_time": "2025-01-04T00:00:01Z",
            },
            # branch B node two - 2025-01-04
            {
                "labels": ["BranchNode"],
                "uuid": "branch_b_node_two",
                "branch": "branch_b",
                "branch_level": 2,
                "from_time": "2025-01-04T01:00:01Z",
            },
        ]

        for node_dict in nodes:
            # ruff: noqa: E501
            create_node_query = """
MATCH (root:Root)
CREATE (n:Node:%(node_labels)s {uuid: $node_dict.uuid})
CREATE (n)-[:IS_PART_OF {status: "active", branch: $node_dict.branch, branch_level: $node_dict.branch_level, from: $node_dict.from_time, to: $node_dict.to_time}]->(root)
            """ % {
                "node_labels": " ".join(node_dict["labels"]),
            }
            await db.execute_query(query=create_node_query, params={"node_dict": node_dict})

        create_relationships_query = """
UNWIND $relationships AS rel
MATCH (source_node:Node {uuid: rel.source_uuid})
MATCH (dest_node:Node {uuid: rel.dest_uuid})
CREATE (rel_node_one:Relationship {uuid: rel.uuid})
CREATE (source_node)-[:IS_RELATED {status: "active", branch: rel.branch, branch_level: rel.branch_level, from: rel.from_time}]->(rel_node_one)
CREATE (rel_node_one)-[:IS_RELATED {status: "active", branch: rel.branch, branch_level: rel.branch_level, from: rel.from_time}]->(dest_node)
// duplicate relationship so the migration will examine them
CREATE (rel_node_two:Relationship {uuid: rel.uuid})
CREATE (source_node)-[:IS_RELATED {status: "active", branch: rel.branch, branch_level: rel.branch_level, from: rel.from_time}]->(rel_node_two)
CREATE (rel_node_two)-[:IS_RELATED {status: "active", branch: rel.branch, branch_level: rel.branch_level, from: rel.from_time}]->(dest_node)
        """

        await db.execute_query(
            query=create_relationships_query,
            params={"relationships": legal_relationship_dicts + illegal_relationship_dicts},
        )

    async def test_migration_033(self, db: InfrahubDatabase, load_bad_data, legal_relationship_dicts) -> None:
        # Run the migration
        migration = Migration033()
        execution_result = await migration.execute(db=db, at=Timestamp())
        assert not execution_result.errors
        validation_result = await migration.validate_migration(db=db)
        assert not validation_result.errors

        all_relationships_query = """
MATCH (r:Relationship)
RETURN r.uuid AS uuid
"""
        results = await db.execute_query(query=all_relationships_query)
        all_relationships = {r["uuid"] for r in results}
        expected_relationships = {r["uuid"] for r in legal_relationship_dicts}
        assert all_relationships == expected_relationships
