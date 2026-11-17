from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

# A literal rather than the diff tracking id classes, because it describes how earlier versions stored these diffs.
CAPTURE_DIFF_TRACKING_ID_PREFIX = "name.selective-regen-capture--"


@dataclass(frozen=True)
class CaptureDiffBatch:
    """A page of deletable diffs and the last selected root's UUID."""

    diffs: list[tuple[str, ...]]
    last_root_uuid: str | None


class GeneratorCaptureDiffsQuery(Query):
    """List the unfrozen capture diffs, each as the uuids of its roots.

    Deleting a root also deletes whatever its partner edge points to, so a diff is listed only when its partner is
    an unfrozen capture root as well.
    """

    name: str = "generator_capture_diffs"
    type: QueryType = QueryType.READ
    insert_return: bool = False

    def __init__(self, limit: int, after_uuid: str | None = None, **kwargs: Any) -> None:
        super().__init__(limit=limit, **kwargs)
        self.params["after_uuid"] = after_uuid

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["tracking_id_prefix"] = CAPTURE_DIFF_TRACKING_ID_PREFIX
        query = """
MATCH (diff_root:DiffRoot)
WHERE diff_root.tracking_id STARTS WITH $tracking_id_prefix
AND (diff_root.is_frozen IS NULL OR diff_root.is_frozen <> TRUE)
AND ($after_uuid IS NULL OR diff_root.uuid > $after_uuid)
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

    def get_batch(self) -> CaptureDiffBatch:
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
        last_root_uuid = self.results[-1].get_as_type(label="root_uuid", return_type=str) if self.results else None
        return CaptureDiffBatch(diffs=sorted(diffs), last_root_uuid=last_root_uuid)


class Migration080(ArbitraryMigration):
    """Delete the diffs that earlier merges stored to find what their post-merge generators wrote.

    Every merge that ran a generator set to execute after merge stored one diff of the default branch, covering
    every change made on it while the generators ran, and nothing read that diff again. Their name tracking id
    carries a prefix that no other diff uses. Each diff is deleted on its own, since one diff can be large and the
    delete query already commits a large diff in several transactions. Cleanup failures are reported for a manual
    retry without blocking the upgrade, since these diffs are unused.
    """

    name: str = "080_delete_generator_capture_diffs"
    description: str = "Delete the diffs stored by earlier merges to find what post-merge generators wrote."
    minimum_version: int = 79

    def build_diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        return DiffRepository(db=db, deserializer=EnrichedDiffDeserializer(parent_adder=DiffParentNodeAdder()))

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        console = migration_input.console

        # One diff failing must not hide the others: the uuids of each failed diff are reported for a re-run.
        errors: list[str] = []
        failed_roots: set[str] = set()
        after_uuid: str | None = None
        diff_repository = self.build_diff_repository(db=db)
        while True:
            try:
                batch = await self._get_capture_diffs(
                    db=db, limit=config.SETTINGS.database.query_size_limit, after_uuid=after_uuid
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Unable to look up the generator capture diffs: {exc}")
                break
            if batch.last_root_uuid is None:
                break
            # Deleting roots changes offsets; advance by the last selected root even when a delete fails.
            after_uuid = batch.last_root_uuid
            console.log(f"Deleting a batch of {len(batch.diffs)} generator capture diff(s)...")
            for root_uuids in batch.diffs:
                if failed_roots.intersection(root_uuids):
                    continue
                try:
                    await diff_repository.delete_diff_roots(diff_root_uuids=list(root_uuids))
                except Exception as exc:  # noqa: BLE001
                    failed_roots.update(root_uuids)
                    errors.append(f"diff with roots {list(root_uuids)}: {exc}")
            del batch

        if errors:
            console.log(f"Generator capture diff cleanup encountered {len(errors)} error(s).")
            for error in errors:
                console.log(error, markup=False)
            console.log("To retry this cleanup, run: infrahub db migrate --migration-number 80")
        return MigrationResult()

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        # Unused capture diffs can remain after a cleanup failure without preventing an upgrade.
        return MigrationResult()

    async def _get_capture_diffs(
        self, db: InfrahubDatabase, limit: int, after_uuid: str | None = None
    ) -> CaptureDiffBatch:
        query = await GeneratorCaptureDiffsQuery.init(db=db, limit=limit, after_uuid=after_uuid)
        await query.execute(db=db)
        return query.get_batch()
