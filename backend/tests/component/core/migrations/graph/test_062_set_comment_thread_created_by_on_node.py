from infrahub.core.migrations.graph.m062_set_comment_thread_created_by_on_node import Migration062
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.timestamp import current_timestamp
from infrahub.database import InfrahubDatabase


async def test_migration_062(db: InfrahubDatabase, default_branch) -> None:
    account1_uuid = "account-uuid-1"
    account2_uuid = "account-uuid-2"
    comment1_uuid = "comment-uuid-1"
    comment2_uuid = "comment-uuid-2"
    thread1_uuid = "thread-uuid-1"
    thread2_uuid = "thread-uuid-2"

    create_test_data_query = """
    CREATE (account1:Node:CoreGenericAccount {uuid: $account1_uuid})
    CREATE (account2:Node:CoreGenericAccount {uuid: $account2_uuid})
    CREATE (comment1:Node:CoreComment {uuid: $comment1_uuid})
    CREATE (comment2:Node:CoreComment {uuid: $comment2_uuid})
    CREATE (thread1:Node:CoreThread {uuid: $thread1_uuid})
    CREATE (thread2:Node:CoreThread {uuid: $thread2_uuid})
    CREATE (rel_c1:Relationship {name: "comment__account"})
    CREATE (rel_c2:Relationship {name: "comment__account"})
    CREATE (rel_t1:Relationship {name: "thread__account"})
    CREATE (rel_t2:Relationship {name: "thread__account"})
    CREATE (comment1)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(rel_c1)
    CREATE (rel_c1)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(account1)
    CREATE (comment2)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(rel_c2)
    CREATE (rel_c2)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(account2)
    CREATE (thread1)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(rel_t1)
    CREATE (rel_t1)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(account1)
    CREATE (thread2)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(rel_t2)
    CREATE (rel_t2)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(account2)
    """
    await db.execute_query(
        query=create_test_data_query,
        params={
            "account1_uuid": account1_uuid,
            "account2_uuid": account2_uuid,
            "comment1_uuid": comment1_uuid,
            "comment2_uuid": comment2_uuid,
            "thread1_uuid": thread1_uuid,
            "thread2_uuid": thread2_uuid,
            "branch": default_branch.name,
            "at": current_timestamp(),
        },
    )

    migration = Migration062()
    await migration.execute(MigrationInput(db=db))
    result = await migration.validate_migration(db=db)
    assert result.success

    verify_comments_query = """
    MATCH (c:CoreComment)
    RETURN c.uuid AS uuid, c.created_by AS created_by
    ORDER BY c.uuid;
    """
    results = await db.execute_query(query=verify_comments_query)
    assert len(results) == 2
    assert results[0].get("uuid") == comment1_uuid
    assert results[0].get("created_by") == account1_uuid
    assert results[1].get("uuid") == comment2_uuid
    assert results[1].get("created_by") == account2_uuid

    verify_threads_query = """
    MATCH (t:CoreThread)
    RETURN t.uuid AS uuid, t.created_by AS created_by
    ORDER BY t.uuid;
    """
    results = await db.execute_query(query=verify_threads_query)
    assert len(results) == 2
    assert results[0].get("uuid") == thread1_uuid
    assert results[0].get("created_by") == account1_uuid
    assert results[1].get("uuid") == thread2_uuid
    assert results[1].get("created_by") == account2_uuid
