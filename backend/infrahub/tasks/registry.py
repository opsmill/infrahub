from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core import registry
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from infrahub.core.branch import Branch

log = get_logger()


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
                branch_registry: Branch = registry.branch[new_branch.name]
                if (
                    branch_registry.schema_hash
                    and branch_registry.schema_hash.main != new_branch.active_schema_hash.main
                ):
                    log.info(
                        "New hash detected",
                        branch=new_branch.name,
                        hash_current=branch_registry.schema_hash.main,
                        hash_new=new_branch.active_schema_hash.main,
                        worker=WORKER_IDENTITY,
                    )
                    await registry.schema.load_schema(db=db, branch=new_branch)
                    registry.branch[new_branch.name] = new_branch
                    schema_branch = registry.schema.get_schema_branch(name=new_branch.name)
                    gqlm = GraphQLSchemaManager.get_manager_for_branch(branch=new_branch, schema_branch=schema_branch)
                    gqlm.get_graphql_schema(
                        include_query=True,
                        include_mutation=True,
                        include_subscription=True,
                        include_types=True,
                    )

            else:
                log.info("New branch detected, pulling schema", branch=new_branch.name, worker=WORKER_IDENTITY)
                await registry.schema.load_schema(db=db, branch=new_branch)
                registry.branch[new_branch.name] = new_branch
                schema_branch = registry.schema.get_schema_branch(name=new_branch.name)
                gqlm = GraphQLSchemaManager.get_manager_for_branch(branch=new_branch, schema_branch=schema_branch)
                gqlm.get_graphql_schema(
                    include_query=True,
                    include_mutation=True,
                    include_subscription=True,
                    include_types=True,
                )

        purged_branches = await registry.purge_inactive_branches(db=db, active_branches=branches)
        purged_branches.update(
            GraphQLSchemaManager.purge_inactive(active_branches=[branch.name for branch in branches])
        )
        for branch_name in sorted(purged_branches):
            log.info(f"Removed branch {branch_name!r} from the registry", branch=branch_name, worker=WORKER_IDENTITY)
