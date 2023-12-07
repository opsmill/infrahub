from typing import TYPE_CHECKING, List

from infrahub import lock
from infrahub.core import registry
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch

log = get_logger()


async def refresh_branches(db: InfrahubDatabase):
    """Pull all the branches from the database and update the registry.

    If a branch is already present with a different value for the hash
    We pull the new schema from the database and we update the registry.
    """

    async with lock.registry.local_schema_lock():
        branches: List[Branch] = await registry.branch_object.get_list(db=db)
        active_branches = [branch.name for branch in branches]
        for new_branch in branches:
            if new_branch.name in registry.branch:
                branch_registry: Branch = registry.branch[new_branch.name]
                if branch_registry.schema_hash and branch_registry.schema_hash.main != new_branch.schema_hash.main:
                    log.info(
                        f"{new_branch.name}: New hash detected OLD {branch_registry.schema_hash.main} >> {new_branch.schema_hash.main} NEW"
                    )
                    registry.branch[new_branch.name] = new_branch

                    await registry.schema.load_schema(db=db, branch=new_branch)

            else:
                registry.branch[new_branch.name] = new_branch
                log.info(f"{new_branch.name}: New branch detected, pulling schema")
                await registry.schema.load_schema(db=db, branch=new_branch)

        for branch_name in list(registry.branch.keys()):
            if branch_name not in active_branches:
                del registry.branch[branch_name]
                log.info(f"Removed branch {branch_name} from the registry")
