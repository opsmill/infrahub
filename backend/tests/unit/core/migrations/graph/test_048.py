<<<<<<< HEAD
from infrahub.core.migrations.graph import Migration048
from infrahub.core.timestamp import current_timestamp
from infrahub.database import InfrahubDatabase


async def test_migration_048(db: InfrahubDatabase, default_branch, person_john_main, car_accord_main) -> None:
    count_is_visible_relationship_query = """
    MATCH ()-[rel:IS_VISIBLE]-()
    RETURN count(*) AS is_visible_count;
    """
    is_visible_count = await db.execute_query(query=count_is_visible_relationship_query)
    assert is_visible_count[0].get("is_visible_count") == 0

    car_name_attr = car_accord_main.get_attribute("name")
    person_name_attr = person_john_main.get_attribute("name")

    add_is_visible_relationship_query = """
    MERGE (bool_true:Boolean { value: true })

    WITH bool_true
    MATCH (attr:Attribute {uuid: $car_name_attr_uuid})
    CREATE (attr)-[:IS_VISIBLE {
      branch: $main_branch,
      branch_level: 1,
      status: "active",
      from: $at
    }]->(bool_true)

    WITH bool_true
    MATCH (attr:Attribute {uuid: $person_name_attr_uuid})
    CREATE (attr)-[:IS_VISIBLE {
      branch: $main_branch,
      branch_level: 1,
      status: "active",
      from: $at
    }]->(bool_true);
    """
    await db.execute_query(
        query=add_is_visible_relationship_query,
        params={
            "main_branch": "main",
            "at": current_timestamp(),
            "car_name_attr_uuid": car_name_attr.id,
            "person_name_attr_uuid": person_name_attr.id,
        },
    )

    is_visible_count = await db.execute_query(query=count_is_visible_relationship_query)
    assert is_visible_count[0].get("is_visible_count") == 4

    migration = Migration048()
    await migration.execute(db=db)
    result = await migration.validate_migration(db=db)
    assert result.success

    is_visible_count = await db.execute_query(query=count_is_visible_relationship_query)
    assert is_visible_count[0].get("is_visible_count") == 0
=======
import pytest

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.migrations.graph.m048_undelete_rel_props import Migration048
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_no_duplicate_paths


class TestMigration048:
    """Test Migration048 to fix Relationship vertices missing IS_VISIBLE/IS_PROTECTED edges
    and remove duplicate IS_RELATED edges.

    The migration should:
    1. Delete duplicate IS_RELATED edges from Relationship vertices
    2. Add missing IS_VISIBLE edges (with value TRUE)
    3. Add missing IS_PROTECTED edges (with value FALSE)
    """

    @pytest.fixture(scope="class")
    async def relationship_dicts(self) -> list[dict[str, str | int | None]]:
        """Test relationships with various scenarios for missing IS_VISIBLE/IS_PROTECTED edges."""
        return [
            # Relationship on main with active IS_RELATED edges - missing both IS_VISIBLE and IS_PROTECTED
            {
                "uuid": "rel_main_missing_both",
                "source_uuid": "main_node_one",
                "dest_uuid": "main_node_two",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-02T00:00:01Z",
                "to_time": None,
                "status": "active",
                "has_visible": False,
                "has_protected": False,
            },
            # Relationship on main with active IS_RELATED edges - missing only IS_VISIBLE
            {
                "uuid": "rel_main_missing_visible",
                "source_uuid": "main_node_one",
                "dest_uuid": "main_node_three",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-02T00:00:02Z",
                "to_time": None,
                "status": "active",
                "has_visible": False,
                "has_protected": True,
            },
            # Relationship on main with active IS_RELATED edges - missing only IS_PROTECTED
            {
                "uuid": "rel_main_missing_protected",
                "source_uuid": "main_node_two",
                "dest_uuid": "main_node_three",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-02T00:00:03Z",
                "to_time": None,
                "status": "active",
                "has_visible": True,
                "has_protected": False,
            },
            # Relationship on main with all edges present (should not be modified)
            {
                "uuid": "rel_main_complete",
                "source_uuid": "main_node_one",
                "dest_uuid": "main_node_four",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-02T00:00:04Z",
                "to_time": None,
                "status": "active",
                "has_visible": True,
                "has_protected": True,
            },
            # Relationship on branch with active IS_RELATED edges - missing both
            {
                "uuid": "rel_branch_missing_both",
                "source_uuid": "branch_node_one",
                "dest_uuid": "branch_node_two",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-03T00:00:01Z",
                "to_time": None,
                "status": "active",
                "has_visible": False,
                "has_protected": False,
            },
            # Relationship with deleted IS_RELATED edges - missing both
            {
                "uuid": "rel_main_deleted_missing_both",
                "source_uuid": "main_node_three",
                "dest_uuid": "main_node_four",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-02T00:00:05Z",
                "to_time": None,
                "status": "deleted",
                "has_visible": False,
                "has_protected": False,
            },
            # Relationship on global branch - missing both
            {
                "uuid": "rel_global_missing_both",
                "source_uuid": "global_node_one",
                "dest_uuid": "global_node_two",
                "branch": GLOBAL_BRANCH_NAME,
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:01Z",
                "to_time": None,
                "status": "active",
                "has_visible": False,
                "has_protected": False,
            },
        ]

    @pytest.fixture(scope="class")
    async def duplicate_edge_relationship_dicts(self) -> list[dict[str, str | int | None]]:
        """Relationships that will have duplicate IS_RELATED edges added."""
        return [
            {
                "uuid": "rel_with_duplicates",
                "source_uuid": "main_node_one",
                "dest_uuid": "main_node_five",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-02T00:00:06Z",
                "to_time": None,
                "status": "active",
                "has_visible": False,
                "has_protected": False,
            },
        ]

    @pytest.fixture(scope="class")
    async def multi_branch_relationship_dict(self) -> dict[str, str | int | None]:
        """Relationship with IS_RELATED edges on multiple branches.

        This simulates a relationship that:
        - Was created on main (active edge)
        - Was deleted on a user branch (deleted edge)

        The migration should create:
        - Active IS_VISIBLE/IS_PROTECTED edges corresponding to the main branch active edge
        - Deleted IS_VISIBLE/IS_PROTECTED edges corresponding to the branch_a deleted edge
        """
        return {
            "uuid": "rel_multi_branch",
            "source_uuid": "main_node_two",
            "dest_uuid": "main_node_five",
            "main_branch": {
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-02T00:00:07Z",
                "to_time": None,
                "status": "active",
            },
            "user_branch": {
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-03T00:00:05Z",
                "to_time": None,
                "status": "deleted",
            },
        }

    @pytest.fixture(scope="class")
    async def load_test_data(
        self,
        db: InfrahubDatabase,
        relationship_dicts: list[dict[str, str | int | None]],
        duplicate_edge_relationship_dicts: list[dict[str, str | int | None]],
        multi_branch_relationship_dict: dict[str, str | int | None],
    ) -> None:
        await delete_all_nodes(db=db)

        # Create root and branches
        root_and_branch_query = """
MERGE (root:Root {default_branch: "main"})
MERGE (main:Branch {name: "main", branched_from: "2023-01-01T00:00:00"})
MERGE (global:Branch {name: "-global-", branched_from: "2023-01-02T00:00:00"})
MERGE (branch_a:Branch {name: "branch_a", branched_from: "2025-01-03T00:00:00"})
        """
        await db.execute_query(query=root_and_branch_query)

        # Create Boolean vertices for IS_VISIBLE and IS_PROTECTED edges
        create_booleans_query = """
MERGE (:Boolean {value: TRUE})
MERGE (:Boolean {value: FALSE})
        """
        await db.execute_query(query=create_booleans_query)

        # Create nodes
        nodes = [
            {
                "labels": ["MainNode"],
                "uuid": "main_node_one",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:00Z",
            },
            {
                "labels": ["MainNode"],
                "uuid": "main_node_two",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:01Z",
            },
            {
                "labels": ["MainNode"],
                "uuid": "main_node_three",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:02Z",
            },
            {
                "labels": ["MainNode"],
                "uuid": "main_node_four",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:03Z",
            },
            {
                "labels": ["MainNode"],
                "uuid": "main_node_five",
                "branch": "main",
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:04Z",
            },
            {
                "labels": ["BranchNode"],
                "uuid": "branch_node_one",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-03T00:00:01Z",
            },
            {
                "labels": ["BranchNode"],
                "uuid": "branch_node_two",
                "branch": "branch_a",
                "branch_level": 2,
                "from_time": "2025-01-03T00:00:02Z",
            },
            {
                "labels": ["GlobalNode"],
                "uuid": "global_node_one",
                "branch": GLOBAL_BRANCH_NAME,
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:00Z",
            },
            {
                "labels": ["GlobalNode"],
                "uuid": "global_node_two",
                "branch": GLOBAL_BRANCH_NAME,
                "branch_level": 1,
                "from_time": "2025-01-01T00:00:01Z",
            },
        ]

        for node_dict in nodes:
            create_node_query = """
MATCH (root:Root)
CREATE (n:Node:%(node_labels)s {uuid: $node_dict.uuid})
CREATE (n)-[:IS_PART_OF {status: "active", branch: $node_dict.branch, branch_level: $node_dict.branch_level, from: $node_dict.from_time}]->(root)
            """ % {"node_labels": ":".join(node_dict["labels"])}
            await db.execute_query(query=create_node_query, params={"node_dict": node_dict})

        # Create relationships with varying IS_VISIBLE/IS_PROTECTED states
        for rel_dict in relationship_dicts:
            create_rel_query = """
MATCH (source_node:Node {uuid: $rel_dict.source_uuid})
MATCH (dest_node:Node {uuid: $rel_dict.dest_uuid})
CREATE (rel:Relationship {uuid: $rel_dict.uuid})
CREATE (source_node)-[:IS_RELATED {
    status: $rel_dict.status, branch: $rel_dict.branch, branch_level: $rel_dict.branch_level,
    from: $rel_dict.from_time, to: $rel_dict.to_time
}]->(rel)
CREATE (rel)-[:IS_RELATED {
    status: $rel_dict.status, branch: $rel_dict.branch, branch_level: $rel_dict.branch_level,
    from: $rel_dict.from_time, to: $rel_dict.to_time
}]->(dest_node)
            """
            await db.execute_query(query=create_rel_query, params={"rel_dict": rel_dict})

            # Add IS_VISIBLE edge if specified
            if rel_dict["has_visible"]:
                add_visible_query = """
MATCH (rel:Relationship {uuid: $uuid})
MATCH (bool:Boolean {value: TRUE})
CREATE (rel)-[:IS_VISIBLE {status: $status, branch: $branch, branch_level: $branch_level, from: $from_time, to: $to_time}]->(bool)
                """
                await db.execute_query(
                    query=add_visible_query,
                    params={
                        "uuid": rel_dict["uuid"],
                        "status": rel_dict["status"],
                        "branch": rel_dict["branch"],
                        "branch_level": rel_dict["branch_level"],
                        "from_time": rel_dict["from_time"],
                        "to_time": rel_dict["to_time"],
                    },
                )

            # Add IS_PROTECTED edge if specified
            if rel_dict["has_protected"]:
                add_protected_query = """
MATCH (rel:Relationship {uuid: $uuid})
MATCH (bool:Boolean {value: FALSE})
CREATE (rel)-[:IS_PROTECTED {status: $status, branch: $branch, branch_level: $branch_level, from: $from_time, to: $to_time}]->(bool)
                """
                await db.execute_query(
                    query=add_protected_query,
                    params={
                        "uuid": rel_dict["uuid"],
                        "status": rel_dict["status"],
                        "branch": rel_dict["branch"],
                        "branch_level": rel_dict["branch_level"],
                        "from_time": rel_dict["from_time"],
                        "to_time": rel_dict["to_time"],
                    },
                )

        # Create relationships with duplicate IS_RELATED edges
        for rel_dict in duplicate_edge_relationship_dicts:
            create_rel_with_dups_query = """
MATCH (source_node:Node {uuid: $rel_dict.source_uuid})
MATCH (dest_node:Node {uuid: $rel_dict.dest_uuid})
CREATE (rel:Relationship {uuid: $rel_dict.uuid})
// Create first set of IS_RELATED edges
CREATE (source_node)-[:IS_RELATED {
    status: $rel_dict.status, branch: $rel_dict.branch, branch_level: $rel_dict.branch_level,
    from: $rel_dict.from_time, to: $rel_dict.to_time
}]->(rel)
CREATE (rel)-[:IS_RELATED {
    status: $rel_dict.status, branch: $rel_dict.branch, branch_level: $rel_dict.branch_level,
    from: $rel_dict.from_time, to: $rel_dict.to_time
}]->(dest_node)
// Create duplicate IS_RELATED edges
CREATE (source_node)-[:IS_RELATED {
    status: $rel_dict.status, branch: $rel_dict.branch, branch_level: $rel_dict.branch_level,
    from: $rel_dict.from_time, to: $rel_dict.to_time
}]->(rel)
CREATE (rel)-[:IS_RELATED {
    status: $rel_dict.status, branch: $rel_dict.branch, branch_level: $rel_dict.branch_level,
    from: $rel_dict.from_time, to: $rel_dict.to_time
}]->(dest_node)
            """
            await db.execute_query(query=create_rel_with_dups_query, params={"rel_dict": rel_dict})

        # Create relationship with IS_RELATED edges on multiple branches (active on main, deleted on branch)
        create_multi_branch_rel_query = """
MATCH (source_node:Node {uuid: $rel_dict.source_uuid})
MATCH (dest_node:Node {uuid: $rel_dict.dest_uuid})
CREATE (rel:Relationship {uuid: $rel_dict.uuid})
// Create active IS_RELATED edges on main branch
CREATE (source_node)-[:IS_RELATED {
    status: $rel_dict.main_branch.status, branch: $rel_dict.main_branch.branch,
    branch_level: $rel_dict.main_branch.branch_level,
    from: $rel_dict.main_branch.from_time, to: $rel_dict.main_branch.to_time
}]->(rel)
CREATE (rel)-[:IS_RELATED {
    status: $rel_dict.main_branch.status, branch: $rel_dict.main_branch.branch,
    branch_level: $rel_dict.main_branch.branch_level,
    from: $rel_dict.main_branch.from_time, to: $rel_dict.main_branch.to_time
}]->(dest_node)
// Create deleted IS_RELATED edges on user branch
CREATE (source_node)-[:IS_RELATED {
    status: $rel_dict.user_branch.status, branch: $rel_dict.user_branch.branch,
    branch_level: $rel_dict.user_branch.branch_level,
    from: $rel_dict.user_branch.from_time, to: $rel_dict.user_branch.to_time
}]->(rel)
CREATE (rel)-[:IS_RELATED {
    status: $rel_dict.user_branch.status, branch: $rel_dict.user_branch.branch,
    branch_level: $rel_dict.user_branch.branch_level,
    from: $rel_dict.user_branch.from_time, to: $rel_dict.user_branch.to_time
}]->(dest_node)
        """
        await db.execute_query(query=create_multi_branch_rel_query, params={"rel_dict": multi_branch_relationship_dict})

    async def test_migration_048(
        self,
        db: InfrahubDatabase,
        load_test_data,
        relationship_dicts: list[dict[str, str | int | None]],
        duplicate_edge_relationship_dicts: list[dict[str, str | int | None]],
        multi_branch_relationship_dict: dict[str, str | int | None],
    ) -> None:
        # Verify initial state - some relationships missing IS_VISIBLE/IS_PROTECTED
        missing_edges_query = """
MATCH (rel:Relationship)
WHERE NOT exists((rel)-[:IS_VISIBLE]->())
OR NOT exists((rel)-[:IS_PROTECTED]->())
RETURN rel.uuid AS uuid
        """
        results = await db.execute_query(query=missing_edges_query)
        missing_edge_uuids = {r["uuid"] for r in results}

        expected_missing = {
            rel["uuid"]
            for rel in relationship_dicts + duplicate_edge_relationship_dicts
            if not rel["has_visible"] or not rel["has_protected"]
        }
        # Add multi-branch relationship to expected missing
        expected_missing.add(multi_branch_relationship_dict["uuid"])
        assert missing_edge_uuids == expected_missing

        # Verify initial state - duplicate IS_RELATED edges exist
        duplicate_edges_in_query = """
MATCH (rel:Relationship {uuid: "rel_with_duplicates"})<-[e:IS_RELATED]-()
RETURN count(e) AS edge_count
        """
        duplicate_edges_out_query = """
MATCH (rel:Relationship {uuid: "rel_with_duplicates"})-[e:IS_RELATED]->()
RETURN count(e) AS edge_count
        """
        results = await db.execute_query(query=duplicate_edges_in_query)
        assert results[0]["edge_count"] == 2  # 2 incoming duplicated
        results = await db.execute_query(query=duplicate_edges_out_query)
        assert results[0]["edge_count"] == 2  # 2 outgoing duplicated

        # Run the migration
        migration = Migration048.init()
        execution_result = await migration.execute(db=db)
        assert not execution_result.errors

        # Verify no duplicate paths remain
        await verify_no_duplicate_paths(db=db)

        # Verify duplicate IS_RELATED edges were removed
        results = await db.execute_query(query=duplicate_edges_in_query)
        assert results[0]["edge_count"] == 1  # 1 incoming
        results = await db.execute_query(query=duplicate_edges_out_query)
        assert results[0]["edge_count"] == 1  # 1 outgoing

        # Verify all relationships now have IS_VISIBLE and IS_PROTECTED edges
        results = await db.execute_query(query=missing_edges_query)
        assert len(results) == 0, f"Relationships still missing edges: {[r['uuid'] for r in results]}"

        # Verify IS_VISIBLE edges have correct value (TRUE)
        verify_visible_query = """
MATCH (rel:Relationship)-[:IS_VISIBLE]->(bool:Boolean)
RETURN rel.uuid AS uuid, bool.value AS value
        """
        results = await db.execute_query(query=verify_visible_query)
        visible_values = {r["uuid"]: r["value"] for r in results}

        all_rel_uuids = {rel["uuid"] for rel in relationship_dicts + duplicate_edge_relationship_dicts}
        all_rel_uuids.add(multi_branch_relationship_dict["uuid"])
        assert set(visible_values.keys()) == all_rel_uuids
        for uuid, value in visible_values.items():
            assert value is True, f"IS_VISIBLE for {uuid} should be TRUE, got {value}"

        # Verify IS_PROTECTED edges have correct value (FALSE)
        verify_protected_query = """
MATCH (rel:Relationship)-[:IS_PROTECTED]->(bool:Boolean)
RETURN rel.uuid AS uuid, bool.value AS value
        """
        results = await db.execute_query(query=verify_protected_query)
        protected_values = {r["uuid"]: r["value"] for r in results}

        assert set(protected_values.keys()) == all_rel_uuids
        for uuid, value in protected_values.items():
            assert value is False, f"IS_PROTECTED for {uuid} should be FALSE, got {value}"

        # Verify edge properties were copied correctly from IS_RELATED edges
        verify_edge_props_query = """
MATCH (rel:Relationship {uuid: $uuid})-[is_related:IS_RELATED]-()
WITH rel, is_related
LIMIT 1
MATCH (rel)-[is_visible:IS_VISIBLE]->()
MATCH (rel)-[is_protected:IS_PROTECTED]->()
RETURN
    is_related.branch AS related_branch,
    is_related.branch_level AS related_branch_level,
    is_related.from AS related_from,
    is_visible.branch AS visible_branch,
    is_visible.branch_level AS visible_branch_level,
    is_visible.from AS visible_from,
    is_protected.branch AS protected_branch,
    is_protected.branch_level AS protected_branch_level,
    is_protected.from AS protected_from
        """

        # Check a relationship that was missing both edges
        results = await db.execute_query(query=verify_edge_props_query, params={"uuid": "rel_main_missing_both"})
        assert len(results) == 1
        result = results[0]
        assert result["visible_branch"] == result["related_branch"]
        assert result["visible_branch_level"] == result["related_branch_level"]
        assert result["visible_from"] == result["related_from"]
        assert result["protected_branch"] == result["related_branch"]
        assert result["protected_branch_level"] == result["related_branch_level"]
        assert result["protected_from"] == result["related_from"]

        # Check branch relationship
        results = await db.execute_query(query=verify_edge_props_query, params={"uuid": "rel_branch_missing_both"})
        assert len(results) == 1
        result = results[0]
        assert result["visible_branch"] == "branch_a"
        assert result["visible_branch_level"] == 2
        assert result["protected_branch"] == "branch_a"
        assert result["protected_branch_level"] == 2

        # Check global branch relationship
        results = await db.execute_query(query=verify_edge_props_query, params={"uuid": "rel_global_missing_both"})
        assert len(results) == 1
        result = results[0]
        assert result["visible_branch"] == GLOBAL_BRANCH_NAME
        assert result["protected_branch"] == GLOBAL_BRANCH_NAME

        # Verify multi-branch relationship has IS_VISIBLE/IS_PROTECTED edges on both branches
        # The migration should create:
        # - Active edges on main branch (corresponding to active IS_RELATED)
        # - Deleted edges on branch_a (corresponding to deleted IS_RELATED)
        verify_multi_branch_edges_query = """
MATCH (rel:Relationship {uuid: $uuid})
OPTIONAL MATCH (rel)-[vis:IS_VISIBLE]->()
OPTIONAL MATCH (rel)-[prot:IS_PROTECTED]->()
WITH rel,
     collect(DISTINCT {branch: vis.branch, status: vis.status, from: vis.from}) AS visible_edges,
     collect(DISTINCT {branch: prot.branch, status: prot.status, from: prot.from}) AS protected_edges
RETURN visible_edges, protected_edges
        """
        results = await db.execute_query(query=verify_multi_branch_edges_query, params={"uuid": "rel_multi_branch"})
        assert len(results) == 1
        result = results[0]

        visible_edges = result["visible_edges"]
        protected_edges = result["protected_edges"]

        # Should have 2 IS_VISIBLE edges: one active on main, one deleted on branch_a
        assert len(visible_edges) == 2, f"Expected 2 IS_VISIBLE edges, got {len(visible_edges)}: {visible_edges}"
        visible_by_branch = {e["branch"]: e for e in visible_edges}
        assert "main" in visible_by_branch, (
            f"Expected IS_VISIBLE edge on main, got branches: {visible_by_branch.keys()}"
        )
        assert "branch_a" in visible_by_branch, f"Expected IS_VISIBLE edge on branch_a, got: {visible_by_branch.keys()}"
        assert visible_by_branch["main"]["status"] == "active"
        assert visible_by_branch["main"]["from"] == multi_branch_relationship_dict["main_branch"]["from_time"]
        assert visible_by_branch["branch_a"]["status"] == "deleted"
        assert visible_by_branch["branch_a"]["from"] == multi_branch_relationship_dict["user_branch"]["from_time"]

        # Should have 2 IS_PROTECTED edges: one active on main, one deleted on branch_a
        assert len(protected_edges) == 2, (
            f"Expected 2 IS_PROTECTED edges, got {len(protected_edges)}: {protected_edges}"
        )
        protected_by_branch = {e["branch"]: e for e in protected_edges}
        assert "main" in protected_by_branch, f"Expected IS_PROTECTED edge on main, got: {protected_by_branch.keys()}"
        assert "branch_a" in protected_by_branch, (
            f"Expected IS_PROTECTED on branch_a, got: {protected_by_branch.keys()}"
        )
        assert protected_by_branch["main"]["status"] == "active"
        assert protected_by_branch["main"]["from"] == multi_branch_relationship_dict["main_branch"]["from_time"]
        assert protected_by_branch["branch_a"]["status"] == "deleted"
        assert protected_by_branch["branch_a"]["from"] == multi_branch_relationship_dict["user_branch"]["from_time"]
>>>>>>> stable
