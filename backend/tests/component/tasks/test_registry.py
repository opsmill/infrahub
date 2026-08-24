import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import NULL_VALUE
from infrahub.core.initialization import create_branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.tasks.registry import refresh_branches


async def test_refresh_branches_continues_past_a_branch_it_cannot_refresh(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The sweep is the only thing that repairs a stale cache entry, so one bad branch must not end it."""
    broken_branch = await create_branch(db=db, branch_name="broken-branch")
    stale_branch = await create_branch(db=db, branch_name="stale-branch")

    # A branch row whose schema hash never reached storage — how the global branch and a graph
    # predating the field look. Reading it back raises from Branch.active_schema_hash
    await db.execute_query(
        query="MATCH (n:Branch {name: $branch_name}) SET n.schema_hash = $null_value",
        params={"branch_name": broken_branch.name, "null_value": NULL_VALUE},
    )
    assert (await Branch.get_by_name(db=db, name=broken_branch.name)).schema_hash is None

    # Something for the sweep to pick up: a rebase timestamp that only exists in the database
    rebased_branch = await Branch.get_by_name(db=db, name=stale_branch.name)
    rebased_branch.branched_from = Timestamp().to_string()
    await rebased_branch.save(db=db)
    assert registry.branch[stale_branch.name].branched_from != rebased_branch.branched_from

    with caplog.at_level("ERROR", logger="infrahub"):
        await refresh_branches(db=db)

    # The branch it gave up on has to be reported, with its traceback: absorbed is not silent
    failures = [
        record.msg
        for record in caplog.records
        if isinstance(record.msg, dict)
        and record.msg.get("event") == f"Failed to refresh branch '{broken_branch.name}' in the registry"
    ]
    assert len(failures) == 1
    assert failures[0]["level"] == "error"
    assert failures[0]["exc_info"]

    assert registry.branch[stale_branch.name].branched_from == rebased_branch.branched_from
