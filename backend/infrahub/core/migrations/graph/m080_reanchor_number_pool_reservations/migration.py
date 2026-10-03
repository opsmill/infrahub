from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from infrahub import config
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.log import get_logger

from .queries import (
    CollapseSharedAttributeRecordsQuery,
    CountedMigrationQuery,
    DeleteLegacyRecordsQuery,
    DeletePoolSourceEdgesQuery,
    LeftoverCountsQuery,
    ReanchorNumberPoolRecordsQuery,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


@dataclass(frozen=True)
class MigrationBehaviour:
    name: str
    query_class: type[CountedMigrationQuery]
    message: str
    failure_message: str


# Pool source edges go before the collapse so their deletion never depends on which records survive it.
BEHAVIORS: tuple[MigrationBehaviour, ...] = (
    MigrationBehaviour(
        name="reanchor_records",
        query_class=ReanchorNumberPoolRecordsQuery,
        message="Re-anchored {count} number pool record(s) onto the attribute they belong to.",
        failure_message="re-anchoring the number pool records",
    ),
    MigrationBehaviour(
        name="delete_pool_source_edges",
        query_class=DeletePoolSourceEdgesQuery,
        message="Deleted {count} stored source edge(s) naming a number pool.",
        failure_message="deleting the legacy number pool source edges",
    ),
    MigrationBehaviour(
        name="collapse_shared_attribute_records",
        query_class=CollapseSharedAttributeRecordsQuery,
        message="Dropped {count} number pool record(s) an attribute held beyond the newest one.",
        failure_message="collapsing the live records sharing one attribute",
    ),
    MigrationBehaviour(
        name="delete_legacy_records",
        query_class=DeleteLegacyRecordsQuery,
        message="Dropped {count} number pool record(s) that no longer reserved a number on any branch.",
        failure_message="dropping the number pool records left on a value vertex",
    ),
)


class Migration080(ArbitraryMigration):
    """Re-anchor every number pool `IS_RESERVED` edge from the shared `AttributeValue` vertex to the owning `Attribute`.

    Only an open edge whose number some branch still holds is moved. Also deletes every stored `HAS_SOURCE`
    edge to a number pool, collapses the live `IS_RESERVED` edges sharing one `Attribute` down to one, and
    deletes every `IS_RESERVED` edge left on an `AttributeValue` vertex.
    """

    name: str = "080_reanchor_number_pool_reservations"
    description: str = "Re-anchor number pool reservation records from the value vertex to the owning attribute"
    minimum_version: int = 79
    behaviors: ClassVar[tuple[MigrationBehaviour, ...]] = BEHAVIORS

    @property
    def batch_size(self) -> int:
        return config.SETTINGS.database.query_size_limit

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        query = await LeftoverCountsQuery.init(db=db)
        await query.execute(db=db)
        if legacy_records := query.legacy_record_count():
            result.errors.append(f"{legacy_records} number pool record(s) are still anchored on a value vertex")
        if pool_source_edges := query.pool_source_edge_count():
            result.errors.append(f"{pool_source_edges} stored source edge(s) still point at a number pool")
        if shared_attribute_records := query.shared_attribute_record_count():
            result.errors.append(
                f"{shared_attribute_records} number pool record(s) still share an attribute with another live record"
            )

        return result

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        console = migration_input.console
        result = MigrationResult()

        for behavior in self.behaviors:
            try:
                query = await behavior.query_class.init(db=db, at=migration_input.at, batch_size=self.batch_size)
                await query.execute(db=db)
            # The legacy-record delete would destroy anything a failed re-anchoring left behind, so a failure stops the run.
            except Exception as exc:  # noqa: BLE001
                console.log(f"Unable to finish {behavior.failure_message}: {exc}")
                result.errors.append(f"{behavior.failure_message}: {exc}")
                break

            count = query.get_count()
            console.log(behavior.message.format(count=count))
            log.info("m080_behaviour_completed", behaviour=behavior.name, count=count)
            result.nbr_migrations_executed += count

        return result
