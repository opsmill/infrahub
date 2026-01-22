from infrahub.core.migrations.graph.m054_set_coreproposedchange_created_by_on_node import Migration054
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.timestamp import current_timestamp
from infrahub.database import InfrahubDatabase


async def test_migration_054(db: InfrahubDatabase, default_branch) -> None:
    account1_uuid = "account-uuid-1"
    account2_uuid = "account-uuid-2"
    pc1_uuid = "pc-uuid-1"
    pc2_uuid = "pc-uuid-2"

    create_test_data_query = """
    CREATE (account1:Node:CoreGenericAccount {uuid: $account1_uuid})
    CREATE (account2:Node:CoreGenericAccount {uuid: $account2_uuid})
    CREATE (pc1:Node:CoreProposedChange {uuid: $pc1_uuid})
    CREATE (pc2:Node:CoreProposedChange {uuid: $pc2_uuid})
    CREATE (rel1:Relationship {name: "coreaccount__proposedchange_created_by"})
    CREATE (rel2:Relationship {name: "coreaccount__proposedchange_created_by"})
    CREATE (pc1)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(rel1)
    CREATE (rel1)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(account1)
    CREATE (pc2)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(rel2)
    CREATE (rel2)-[:IS_RELATED {branch: $branch, branch_level: 1, status: "active", from: $at}]->(account2)
    """
    await db.execute_query(
        query=create_test_data_query,
        params={
            "account1_uuid": account1_uuid,
            "account2_uuid": account2_uuid,
            "pc1_uuid": pc1_uuid,
            "pc2_uuid": pc2_uuid,
            "branch": default_branch.name,
            "at": current_timestamp(),
        },
    )

    migration = Migration054()
    await migration.execute(MigrationInput(db=db))
    result = await migration.validate_migration(db=db)
    assert result.success

    verify_query = """
    MATCH (pc:CoreProposedChange)
    RETURN pc.uuid AS uuid, pc.created_by AS created_by
    ORDER BY pc.uuid;
    """
    results = await db.execute_query(query=verify_query)
    assert len(results) == 2
    assert results[0].get("uuid") == pc1_uuid
    assert results[0].get("created_by") == account1_uuid
    assert results[1].get("uuid") == pc2_uuid
    assert results[1].get("created_by") == account2_uuid
