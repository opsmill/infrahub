from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core import registry
from infrahub.log import get_logger
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

log = get_logger()


def update_graphql_schema(branch: Branch, schema_branch: SchemaBranch) -> None:
    """
    Update the GraphQL schema for the given branch.
    """
    from infrahub.graphql.manager import GraphQLSchemaManager

    gqlm = GraphQLSchemaManager.get_manager_for_branch(branch=branch, schema_branch=schema_branch)
    gqlm.get_graphql_schema(
        include_query=True,
        include_mutation=True,
        include_subscription=True,
        include_types=True,
    )


async def create_branch_registry(db: InfrahubDatabase, branch: Branch) -> None:
    """Create a new entry in the registry for a given branch."""

    log.info("New branch detected, pulling schema", branch=branch.name, worker=WORKER_IDENTITY)
    await registry.schema.load_schema(db=db, branch=branch)
    registry.branch[branch.name] = branch
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    update_graphql_schema(branch=branch, schema_branch=schema_branch)


async def update_branch_registry(db: InfrahubDatabase, branch: Branch) -> None:
    """Update the registry for a branch if the schema hash has changed."""

    existing_branch: Branch = registry.branch[branch.name]

    if not existing_branch.schema_hash:
        log.warning("Branch schema hash is not set, cannot update branch registry")
        return

    if existing_branch.schema_hash and existing_branch.schema_hash.main == branch.active_schema_hash.main:
        log.debug(
            "Branch schema hash is the same, no need to update branch registry",
            branch=branch.name,
            hash=existing_branch.schema_hash.main,
            worker=WORKER_IDENTITY,
        )
        return

    log.info(
        "New hash detected",
        branch=branch.name,
        hash_current=existing_branch.schema_hash.main,
        hash_new=branch.active_schema_hash.main,
        worker=WORKER_IDENTITY,
    )
    await registry.schema.load_schema(db=db, branch=branch)
    registry.branch[branch.name] = branch
    schema_branch = registry.schema.get_schema_branch(name=branch.name)

    update_graphql_schema(branch=branch, schema_branch=schema_branch)


async def refresh_branches(db: InfrahubDatabase) -> None:
    """Pull all the branches from the database and update the registry.

    If a branch is already present with a different value for the hash
    We pull the new schema from the database and we update the registry.
    """
    from infrahub.graphql.manager import GraphQLSchemaManager

    async with lock.registry.local_schema_lock():
        branches = await registry.branch_object.get_list(db=db)
        for new_branch in branches:
            if new_branch.name in registry.branch:
                await update_branch_registry(db=db, branch=new_branch)
            else:
                await create_branch_registry(db=db, branch=new_branch)

        purged_branches = await registry.purge_inactive_branches(db=db, active_branches=branches)
        purged_branches.update(
            GraphQLSchemaManager.purge_inactive(active_branches=[branch.name for branch in branches])
        )
        for branch_name in sorted(purged_branches):
            log.info(f"Removed branch {branch_name!r} from the registry", branch=branch_name, worker=WORKER_IDENTITY)
