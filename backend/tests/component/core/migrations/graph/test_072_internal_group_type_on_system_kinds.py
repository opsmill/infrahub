from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.graph.m072_internal_group_type_on_system_kinds import (
    INTERNAL_GROUP_KINDS,
    Migration072,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.timestamp import current_timestamp
from infrahub.database import InfrahubDatabase


async def test_migration_072(db: InfrahubDatabase, default_branch: Branch) -> None:
    """System-managed groups flip to 'internal'; CoreStandardGroup is left untouched."""
    create_test_data_query = """
    // shared 'default' value reused by every group_type attribute below
    CREATE (default_value:AttributeValue:AttributeValueIndexed {value: "default", is_default: true})

    // one instance per system-managed kind, plus a user-managed CoreStandardGroup as a control.
    CREATE (generator:Node:CoreGeneratorGroup {uuid: "generator-uuid"})
    CREATE (generator_aware:Node:CoreGeneratorAwareGroup {uuid: "generator-aware-uuid"})
    CREATE (graphql:Node:CoreGraphQLQueryGroup {uuid: "graphql-uuid"})
    CREATE (repository:Node:CoreRepositoryGroup {uuid: "repository-uuid"})
    CREATE (standard:Node:CoreStandardGroup {uuid: "standard-uuid"})

    CREATE (generator_attr:Attribute {name: "group_type"})
    CREATE (generator_aware_attr:Attribute {name: "group_type"})
    CREATE (graphql_attr:Attribute {name: "group_type"})
    CREATE (repository_attr:Attribute {name: "group_type"})
    CREATE (standard_attr:Attribute {name: "group_type"})

    CREATE (generator)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(generator_attr)
    CREATE (generator_aware)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(generator_aware_attr)
    CREATE (graphql)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(graphql_attr)
    CREATE (repository)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(repository_attr)
    CREATE (standard)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(standard_attr)

    CREATE (generator_attr)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(default_value)
    CREATE (generator_aware_attr)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(default_value)
    CREATE (graphql_attr)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(default_value)
    CREATE (repository_attr)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(default_value)
    CREATE (standard_attr)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(default_value)
    """
    await db.execute_query(
        query=create_test_data_query,
        params={"branch": default_branch.name, "at": current_timestamp()},
    )

    migration = Migration072()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    # every system-managed kind should now resolve to group_type='internal'
    affected_query = """
    MATCH (n:Node)
    WHERE any(label IN labels(n) WHERE label IN $kinds)
    MATCH (n)-[:HAS_ATTRIBUTE]->(:Attribute {name: "group_type"})-[hv:HAS_VALUE]->(v:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL
    RETURN n.uuid AS uuid, v.value AS group_type
    ORDER BY n.uuid
    """
    results = await db.execute_query(query=affected_query, params={"kinds": INTERNAL_GROUP_KINDS})
    assert len(results) == 4
    for row in results:
        assert row.get("group_type") == "internal"

    # the CoreStandardGroup control must still read 'default'
    control_query = """
    MATCH (n:Node:CoreStandardGroup {uuid: "standard-uuid"})
    MATCH (n)-[:HAS_ATTRIBUTE]->(:Attribute {name: "group_type"})-[hv:HAS_VALUE]->(v:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL
    RETURN v.value AS group_type
    """
    results = await db.execute_query(query=control_query)
    assert len(results) == 1
    assert results[0].get("group_type") == "default"


async def test_migration_072_branch_isolation(db: InfrahubDatabase, default_branch: Branch) -> None:
    """execute() leaves non-default-branch edges alone; execute_against_branch flips them."""
    feature_branch = await create_branch(db=db, branch_name="feature-branch")

    create_branched_instance_query = """
    CREATE (default_value:AttributeValue:AttributeValueIndexed {value: "default", is_default: true})

    CREATE (repo:Node:CoreRepositoryGroup {uuid: "repo-branched-uuid"})
    CREATE (repo_attr:Attribute {name: "group_type"})

    CREATE (repo)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 2, status: "active", from: $at}]->(repo_attr)
    CREATE (repo_attr)-[:HAS_VALUE {branch: $branch, branch_level: 2, status: "active", from: $at}]->(default_value)
    """
    await db.execute_query(
        query=create_branched_instance_query,
        params={"branch": feature_branch.name, "at": current_timestamp()},
    )

    migration = Migration072()

    # default-branch pass must leave the feature-branch edge alone
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    branched_query = """
    MATCH (n:Node:CoreRepositoryGroup {uuid: "repo-branched-uuid"})
    MATCH (n)-[:HAS_ATTRIBUTE]->(:Attribute {name: "group_type"})-[hv:HAS_VALUE]->(v:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL
    RETURN v.value AS group_type, hv.branch AS branch
    """
    results = await db.execute_query(query=branched_query)
    assert len(results) == 1
    assert results[0].get("group_type") == "default"
    assert results[0].get("branch") == feature_branch.name

    # per-branch pass flips it
    branch_result = await migration.execute_against_branch(migration_input=MigrationInput(db=db), branch=feature_branch)
    assert not branch_result.errors

    results = await db.execute_query(query=branched_query)
    assert len(results) == 1
    assert results[0].get("group_type") == "internal"
    assert results[0].get("branch") == feature_branch.name
