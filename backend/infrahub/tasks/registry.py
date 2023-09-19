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
            if new_branch.name in registry.branch:
                branch_registry: Branch = registry.branch[new_branch.name]
                if branch_registry.schema_hash and branch_registry.schema_hash.main != new_branch.schema_hash.main:
                    log.info(
                        f"{new_branch.name}: New hash detected OLD {branch_registry.schema_hash.main} >> {new_branch.schema_hash.main} NEW"
                    )
                    registry.branch[new_branch.name] = new_branch
                    schema_diff = branch_registry.schema_hash.compare(new_branch.schema_hash)
                    await registry.schema.load_schema_from_db(
                        session=session, branch=new_branch, schema_diff=schema_diff
                    )

            else:
                registry.branch[new_branch.name] = new_branch

                # Check if the Origin Branch is present in the registry and if the main hash is the same
                if (
                    new_branch.origin_branch in registry.branch
                    and registry.branch[new_branch.origin_branch].schema_hash.main == new_branch.schema_hash.main
                ):
                    log.info(f"{new_branch.name}: New branch detected, pulling schema from cache")
                    origin_branch: Branch = registry.branch[new_branch.origin_branch]
                    origin_schema = registry.schema.get_schema_branch(name=origin_branch.name)
                    new_branch_schema = origin_schema.duplicate()
                    registry.schema.set_schema_branch(name=new_branch.name, schema=new_branch_schema)

                else:
                    log.info(f"{new_branch.name}: New branch detected, pulling schema from db")
                    await registry.schema.load_schema_from_db(session=session, branch=new_branch)

        for branch_name in list(registry.branch.keys()):
            if branch_name not in active_branches:
                del registry.branch[branch_name]
                log.info(f"Removed branch {branch_name} from the registry")
