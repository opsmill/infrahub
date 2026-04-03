from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase, QueryType


async def test_duplicate_branch_name_rejected(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Saving two branches with the same name must result in only one branch in the database.

    The production create_branch flow (in core/branch/tasks.py) uses a TOCTOU pattern:
    it checks Branch.get_by_name() then creates the branch, with no atomicity guarantee.
    Concurrent requests can both pass the check before either branch is saved.

    The underlying problem is that the database layer has no uniqueness constraint on
    Branch.name — the StandardNodeCreateQuery uses a bare CREATE statement. This test
    demonstrates the vulnerability by saving two Branch nodes with the same name.

    Expected behavior: the database should contain exactly one branch with this name,
    either because the second save is rejected or because a MERGE is used instead of CREATE.

    On buggy code, both saves succeed and the database contains two branches with the
    same name.
    """
    branch_name = "duplicate-test-branch"

    # Create and save the first branch
    branch1 = Branch(
        name=branch_name,
        status=BranchStatus.OPEN,
        hierarchy_level=2,
        description="First branch",
        is_default=False,
        sync_with_git=False,
    )
    branch1.update_schema_hash()
    await branch1.save(db=db)

    # Attempt to create and save a second branch with the same name.
    # The fix could either:
    #   1. Add a Neo4j uniqueness constraint that rejects the second CREATE, or
    #   2. Use a distributed lock in the create_branch flow, or
    #   3. Use MERGE instead of CREATE in the Cypher query
    # Regardless of approach, only one branch with this name should exist afterward.
    branch2 = Branch(
        name=branch_name,
        status=BranchStatus.OPEN,
        hierarchy_level=2,
        description="Second branch (duplicate)",
        is_default=False,
        sync_with_git=False,
    )
    branch2.update_schema_hash()
    try:
        await branch2.save(db=db)
    except Exception:
        # If the save raises an error (e.g., uniqueness constraint), that's acceptable.
        pass

    # The critical assertion: exactly one branch with this name should exist in the database.
    query = "MATCH (n:Branch) WHERE n.name = $name RETURN n"
    db_results = await db.execute_query(
        query=query, params={"name": branch_name}, name="test_count_branches", type=QueryType.READ
    )
    assert len(db_results) == 1, (
        f"Expected exactly 1 branch named '{branch_name}' in the database, "
        f"but found {len(db_results)}. The database allows duplicate branch names, "
        f"which is the root cause of the race condition in branch creation."
    )
