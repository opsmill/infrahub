from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.branch.data_deleter import BranchDataDeleter, BranchDataDeleterInterface
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult, get_migration_console
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

console = get_migration_console()


class DeletingBranchNamesQuery(Query):
    """Find the branches whose delete never finished."""

    name: str = "deleting_branch_names"
    insert_return: bool = False
    type: QueryType = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
MATCH (b:Branch)
WHERE b.status = $deleting_status
RETURN b.name AS branch_name
        """
        self.params["deleting_status"] = BranchStatus.DELETING.value
        self.add_to_query(query)
        self.update_return_labels("branch_name")
        self.order_by = ["branch_name"]

    def get_branch_names(self) -> list[str]:
        return [result.get_as_type(label="branch_name", return_type=str) for result in self.get_results()]


class Migration075(ArbitraryMigration):
    """Finish deleting branches that a previous branch delete left unfinished.

    A branch delete used to run as one query whose memory use grew with the size of the branch, so
    on a large branch it could exhaust the transaction memory pool and fail part way through. The
    branch was left with the DELETING status, which hides it from the branch list, and with however
    much of its data the failed run had not yet reached. Nothing retried it, and the branch could not
    be deleted again because it was no longer possible to look up.
    """

    name: str = "075_finish_deleting_branches"
    description: str = "Finish deleting branches whose delete failed part way through."
    minimum_version: int = 74

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    def build_deleter(self, db: InfrahubDatabase) -> BranchDataDeleterInterface:
        return BranchDataDeleter(db=db, batch_size=config.SETTINGS.database.query_size_limit)

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db

        try:
            names_query = await DeletingBranchNamesQuery.init(db=db)
            await names_query.execute(db=db)
            branch_names = names_query.get_branch_names()
        except Exception as exc:  # noqa: BLE001 - a lookup failure is reported, never raised out of a migration
            return MigrationResult(errors=[f"Unable to look up branches in the DELETING state: {exc}"])

        if not branch_names:
            return MigrationResult()

        console.log(f"Found {len(branch_names)} branch(es) left in the DELETING state: {branch_names}")

        # One branch failing must not hide the others: each is deleted in its own right, and the
        # names of those that failed are reported so a re-run has something to act on.
        errors: list[str] = []
        deleter = self.build_deleter(db=db)
        for branch_name in branch_names:
            console.log(f"Cleaning up branch '{branch_name}' left in the DELETING state...")
            try:
                branch = await Branch.get_by_name(db=db, name=branch_name, ignore_deleting=False)
<<<<<<< HEAD
                delete_result = await deleter.delete(branch=branch)
            except Exception as exc:  # noqa: BLE001 - see the comment above: one branch must not hide the others
=======
                delete_result = await deleter.delete(branch=branch, user_id=migration_input.user_id)
            except Exception as exc:
>>>>>>> stable
                console.log(f"Branch '{branch_name}' could not be deleted: {exc}")
                errors.append(f"branch '{branch_name}': {exc}")
                continue
            if delete_result.branch_deleted:
                console.log(f"Branch '{branch_name}' deleted, {delete_result.edges_removed} edge(s) removed.")
            else:
                console.log(f"Branch '{branch_name}' was already gone, {delete_result.edges_removed} edge(s) removed.")

        return MigrationResult(errors=errors)
