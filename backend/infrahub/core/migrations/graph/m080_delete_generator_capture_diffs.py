from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

# A literal rather than the diff tracking id classes, because it describes how earlier versions stored these diffs.
CAPTURE_DIFF_TRACKING_ID_PREFIX = "name.selective-regen-capture--"


class GeneratorCaptureDiffsQuery(Query):
    """List the unfrozen capture diffs, each as the uuids of its roots.

    Deleting a root also deletes whatever its partner edge points to, so a diff is listed only when its partner is
    an unfrozen capture root as well.
    """

    name: str = "generator_capture_diffs"
    type: QueryType = QueryType.READ
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["tracking_id_prefix"] = CAPTURE_DIFF_TRACKING_ID_PREFIX
        query = """
MATCH (diff_root:DiffRoot)
WHERE diff_root.tracking_id STARTS WITH $tracking_id_prefix
AND (diff_root.is_frozen IS NULL OR diff_root.is_frozen <> TRUE)
OPTIONAL MATCH (diff_root)-[:DIFF_HAS_PARTNER]-(partner:DiffRoot)
WITH diff_root, collect(partner) AS partners
WHERE all(
    partner IN partners
    WHERE partner.tracking_id STARTS WITH $tracking_id_prefix
    AND (partner.is_frozen IS NULL OR partner.is_frozen <> TRUE)
)
RETURN diff_root.uuid AS root_uuid, [partner IN partners | partner.uuid] AS partner_uuids
        """
        self.add_to_query(query)
        self.return_labels = ["root_uuid", "partner_uuids"]
        self.order_by = ["root_uuid"]

    def get_diffs(self) -> list[tuple[str, ...]]:
        diffs = {
            tuple(
                sorted(
                    {
                        result.get_as_type(label="root_uuid", return_type=str),
                        *result.get_as_list_of_type("partner_uuids", str),
                    }
                )
            )
            for result in self.get_results()
        }
        return sorted(diffs)


class Migration080(ArbitraryMigration):
    """Delete the diffs that earlier merges stored to find what their post-merge generators wrote.

    Every merge that ran a generator set to execute after merge stored one diff of the default branch, covering
    every change made on it while the generators ran, and nothing read that diff again. Their name tracking id
    carries a prefix that no other diff uses. Each diff is deleted on its own, since one diff can be large and the
    delete query already commits a large diff in several transactions.
    """

    name: str = "080_delete_generator_capture_diffs"
    description: str = "Delete the diffs stored by earlier merges to find what post-merge generators wrote."
    minimum_version: int = 79

    def build_diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        return DiffRepository(db=db, deserializer=EnrichedDiffDeserializer(parent_adder=DiffParentNodeAdder()))

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        console = migration_input.console

        try:
            diffs = await self._get_capture_diffs(db=db)
        except Exception as exc:
            return MigrationResult(errors=[f"Unable to look up the generator capture diffs: {exc}"])

        if not diffs:
            return MigrationResult()

        console.log(f"Deleting {len(diffs)} generator capture diff(s)...")
        # One diff failing must not hide the others: the uuids of each failed diff are reported for a re-run.
        errors: list[str] = []
        diff_repository = self.build_diff_repository(db=db)
        for root_uuids in diffs:
            try:
                await diff_repository.delete_diff_roots(diff_root_uuids=list(root_uuids))
            except Exception as exc:
                errors.append(f"diff with roots {list(root_uuids)}: {exc}")
        if errors:
            console.log(f"{len(errors)} generator capture diff(s) could not be deleted.")

        return MigrationResult(errors=errors)

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()
        remaining = await self._get_capture_diffs(db=db)
        if remaining:
            result.errors.append(
                f"{len(remaining)} generator capture diff(s) remain: {[list(root_uuids) for root_uuids in remaining]}"
            )
        return result

    async def _get_capture_diffs(self, db: InfrahubDatabase) -> list[tuple[str, ...]]:
        query = await GeneratorCaptureDiffsQuery.init(db=db)
        await query.execute(db=db)
        return query.get_diffs()
