from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.query.delete import DeleteAfterTimeQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry


class DatabaseResetter:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_diff_repository(self) -> DiffRepository:
        default_branch = await Branch.get_by_name(db=self.db, name=registry.default_branch)
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=self.db, branch=default_branch)

    async def reset_to_time(self, reset_time: Timestamp) -> None:
        # delete any diff that covers a time period after the to_time
        diff_repository = await self.get_diff_repository()
        all_diff_metadatas = await diff_repository.get_roots_metadata(exclude_merged=False)
        diff_uuids_to_delete = [d.uuid for d in all_diff_metadatas if d.to_time > reset_time]
        await diff_repository.delete_diff_roots(diff_uuids_to_delete)

        # remove any changes from the database after the to_time
        query_delete = await DeleteAfterTimeQuery.init(db=self.db, timestamp=reset_time)
        await query_delete.execute(db=self.db)
