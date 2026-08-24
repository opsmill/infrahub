from uuid import uuid4

from fast_depends import Provider

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.tasks import migrate_branch
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.initialization import create_branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.workers.dependencies import build_database


async def test_migrate_branch_publishes_migrated_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    """The flow migrates an instance of its own, so it has to publish that instance itself."""
    branch = await create_branch(db=db, branch_name="migrate-branch")
    assert registry.branch[branch.name] is branch

    # A branch as an upgrade leaves it behind: its graph version trails the application
    branch.graph_version = GRAPH_VERSION - 1
    await branch.save(db=db)

    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with dependency_provider.scope(build_database, lambda singleton=True: db):  # noqa: ARG005
        await migrate_branch(branch=branch.name, context=context, send_events=False)

    migrated_branch = await Branch.get_by_name(db=db, name=branch.name)
    assert migrated_branch.graph_version == GRAPH_VERSION
    assert migrated_branch.status is BranchStatus.OPEN

    published_branch = registry.branch[branch.name]
    assert published_branch.graph_version == GRAPH_VERSION
    assert published_branch.status is BranchStatus.OPEN
