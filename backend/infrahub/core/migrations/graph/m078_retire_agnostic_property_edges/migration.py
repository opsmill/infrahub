from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.branch.data_deleter import MAX_AGNOSTIC_PEER_BATCH_SIZE
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult

from .queries import CloseUnretainedAgnosticFieldsQuery, DeleteDetachedAgnosticFieldsQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration078(ArbitraryMigration):
    """Release the branch-agnostic values that earlier versions left reserved forever.

    A branch-agnostic attribute or relationship keeps its value on edges carrying the global branch
    name, which every branch reads. Deleting the owning object, or removing the field from the
    schema, used to tombstone at branch level and leave those global edges open, so the value stayed
    reserved with nothing able to read it -- blocking uniqueness constraints and holding pool values
    out of circulation. Two shapes of that backlog are repaired here:

    - a field no branch can still reach over a live owner -- one live owner for an attribute, two
      distinct live peers for a relationship, so a relationship left with a single arm qualifies
      while both of its owners are still live -- has its remaining open global edges closed, the
      half-closed vertices (owning edge closed with property edges still open, or the reverse)
      included;
    - a field vertex with no linked node vertex at all -- what a branch deletion predating the
      agnostic-peer cleanup left behind -- is hard-deleted, since nothing can reach, diff, or
      time-travel to it.

    Retention is judged across every branch, so a value any branch can still read is left open and
    released later by the runtime enforcement points. Each close is stamped with the time the field
    stopped being reachable rather than with the upgrade's own time, which keeps it out of the fork
    window of every branch older than the upgrade. Where the graph records no such time the
    upgrade's own time is the fallback, which shifts no branch's view either: a field only reaches
    the stamp once no branch retains it. A second run reports zero repairs.
    """

    name: str = "078_retire_agnostic_property_edges"
    description: str = "Release the branch-agnostic attribute and relationship values no branch can still read"
    minimum_version: int = 77

    @property
    def batch_size(self) -> int:
        return min(config.SETTINGS.database.query_size_limit, MAX_AGNOSTIC_PEER_BATCH_SIZE)

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        """Always clean: a repair the graph cannot complete must not fail the upgrade."""
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        console = migration_input.console
        result = MigrationResult()

        # Each pass runs whatever the one before it did, but only the repairs decide the outcome.
        try:
            close_query = await CloseUnretainedAgnosticFieldsQuery.init(
                db=db, at=migration_input.at, batch_size=self.batch_size, user_id=migration_input.user_id
            )
            await close_query.execute(db=db)
        # don't kill the migration on one query failure. it's idempotent so it can just go again.
        except Exception as exc:  # noqa: BLE001
            console.log(f"Unable to close the unretained branch-agnostic edges: {exc}")
            result.errors.append(f"closing unretained branch-agnostic edges: {exc}")
        else:
            edges_closed = close_query.closed_edge_count()
            result.nbr_migrations_executed += edges_closed
            console.log(f"Closed {edges_closed} branch-agnostic edge(s) that no branch could still read.")

        try:
            delete_query = await DeleteDetachedAgnosticFieldsQuery.init(db=db, batch_size=self.batch_size)
            await delete_query.execute(db=db)
        # don't kill the migration on one query failure. it's idempotent so it can just go again.
        except Exception as exc:  # noqa: BLE001
            console.log(f"Unable to remove the detached branch-agnostic vertices: {exc}")
            result.errors.append(f"removing detached branch-agnostic vertices: {exc}")
        else:
            vertices_removed = delete_query.removed_vertex_count()
            result.nbr_migrations_executed += vertices_removed
            console.log(f"Removed {vertices_removed} attribute or relationship vertex/vertices with no linked object.")

        return result
