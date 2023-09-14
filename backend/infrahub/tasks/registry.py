from typing import List

from neo4j import AsyncSession

from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.log import get_logger

log = get_logger()


async def refresh_branches(session: AsyncSession):
    """Pull all the branches from the database and update the registry.

    If a branch is already present with a different value for the hash
    We pull the new schema from the database and we update the registry.
    """

    async with lock.registry.local_schema_lock():
        branches: List[Branch] = await Branch.get_list(session=session)
        active_branches = [branch.name for branch in branches]
        for new_branch in branches:
            branch_already_present = new_branch.name in registry.branch

            if branch_already_present:
                if registry.branch[new_branch.name].schema_hash != new_branch.schema_hash:
                    log.info(
                        f"{new_branch.name}: New hash detected OLD {registry.branch[new_branch.name].schema_hash} >> {new_branch.schema_hash} NEW"
                    )
                    registry.branch[new_branch.name] = new_branch
                    await registry.schema.load_schema_from_db(session=session, branch=new_branch)

            else:
                log.info(f"{new_branch.name}: New branch detected")
                registry.branch[new_branch.name] = new_branch
                await registry.schema.load_schema_from_db(session=session, branch=new_branch)

        for branch_name in list(registry.branch.keys()):
            if branch_name not in active_branches:
                del registry.branch[branch_name]
                log.info(f"Removed branch {branch_name} from the registry")
