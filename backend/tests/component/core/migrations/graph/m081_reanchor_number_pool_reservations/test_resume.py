"""Re-running the number pool re-anchoring migration after it failed part way through."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, ClassVar, Self

import pytest

from infrahub.core.migrations.graph.m081_reanchor_number_pool_reservations import Migration081
from infrahub.core.migrations.graph.m081_reanchor_number_pool_reservations.queries import (
    CollapseSharedAttributeRecordsQuery,
    CountedMigrationQuery,
    DeleteLegacyRecordsQuery,
    DeletePoolSourceEdgesQuery,
    ReanchorNumberPoolRecordsQuery,
)
from infrahub.core.timestamp import Timestamp
from tests.component.core.migrations.graph.m081_reanchor_number_pool_reservations.conftest import (
    attribute_id_of,
    create_legacy_record,
    create_legacy_source_edge,
    create_pool,
    create_ticket,
    live_records,
    reservation_records,
    rewrite_records_to_legacy_shape,
    run_migration,
    stored_source_pool_ids,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.migrations.graph.m081_reanchor_number_pool_reservations.migration import MigrationBehaviour
    from infrahub.database import InfrahubDatabase


@dataclass
class FailedBehaviourTestCase:
    name: str
    failing_query: type[CountedMigrationQuery]
    error: str
    validation_errors: list[str]
    """What validation finds once the run has stopped at the failing behaviour."""


FAILED_BEHAVIOUR_TEST_CASES: list[FailedBehaviourTestCase] = [
    FailedBehaviourTestCase(
        name="reanchor_records",
        failing_query=ReanchorNumberPoolRecordsQuery,
        error="re-anchoring the number pool records: injected failure",
        validation_errors=[
            "3 number pool record(s) are still anchored on a value vertex",
            "1 stored source edge(s) still point at a number pool",
        ],
    ),
    FailedBehaviourTestCase(
        name="delete_pool_source_edges",
        failing_query=DeletePoolSourceEdgesQuery,
        error="deleting the legacy number pool source edges: injected failure",
        validation_errors=[
            "1 number pool record(s) are still anchored on a value vertex",
            "1 stored source edge(s) still point at a number pool",
            "1 number pool record(s) still share an attribute with another live record",
        ],
    ),
    FailedBehaviourTestCase(
        name="collapse_shared_attribute_records",
        failing_query=CollapseSharedAttributeRecordsQuery,
        error="collapsing the live records sharing one attribute: injected failure",
        validation_errors=[
            "1 number pool record(s) are still anchored on a value vertex",
            "1 number pool record(s) still share an attribute with another live record",
        ],
    ),
    FailedBehaviourTestCase(
        name="delete_legacy_records",
        failing_query=DeleteLegacyRecordsQuery,
        error="dropping the number pool records left on a value vertex: injected failure",
        validation_errors=["1 number pool record(s) are still anchored on a value vertex"],
    ),
]


class FailingQuery(CountedMigrationQuery):
    name: str = "m081_failing_query"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        pass

    async def execute(self, db: InfrahubDatabase, timeout_seconds: float | None = None) -> Self:
        raise RuntimeError("injected failure")


def migration_failing_at(query_class: type[CountedMigrationQuery]) -> Migration081:
    """The migration with the behaviour that runs `query_class` swapped for one that raises."""

    class FailingMigration081(Migration081):
        behaviors: ClassVar[tuple[MigrationBehaviour, ...]] = tuple(
            replace(behaviour, query_class=FailingQuery) if behaviour.query_class is query_class else behaviour
            for behaviour in Migration081.behaviors
        )

    return FailingMigration081()


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FAILED_BEHAVIOUR_TEST_CASES])
async def test_a_failed_behaviour_stops_the_run_and_a_rerun_finishes_it(
    db: InfrahubDatabase,
    default_branch: Branch,
    ticket_schema: None,
    test_case: FailedBehaviourTestCase,
) -> None:
    pool = await create_pool(db=db, name="ticket-pool")
    ticket = await create_ticket(db=db, title="held", pool=pool)
    assert await rewrite_records_to_legacy_shape(db=db) == 1
    await create_legacy_record(db=db, pool_id=pool.id, node_id=ticket.id, at=Timestamp().subtract(seconds=60))
    await create_legacy_record(db=db, pool_id=pool.id, node_id=ticket.id, identifier=str(uuid.uuid4()))
    await create_legacy_source_edge(db=db, node_id=ticket.id, pool_id=pool.id, branch=default_branch)

    failed_run = await run_migration(db=db, migration=migration_failing_at(test_case.failing_query))

    assert failed_run.result.errors == [test_case.error]
    assert failed_run.output.count("Unable to finish") == 1
    assert failed_run.validation.errors == test_case.validation_errors

    rerun = await run_migration(db=db)
    assert not rerun.result.errors
    assert not rerun.validation.errors

    records = await reservation_records(db=db)
    assert [(record.anchor, record.attribute_id) for record in live_records(records)] == [
        ("Attribute", attribute_id_of(node=ticket))
    ]
    assert len(records) == 1, "the duplicate and the orphan must both be gone"
    assert await stored_source_pool_ids(db=db, node_id=ticket.id) == []


async def test_a_rerun_after_some_records_moved_moves_only_the_rest(
    db: InfrahubDatabase, default_branch: Branch, ticket_schema: None
) -> None:
    """Starting from a half-moved state, a run moves only the legacy edges and leaves the moved ones as they are.

    The state is built directly rather than by interrupting a run: it is the shape a run stopped between
    batches leaves, because each batch moves its edges completely or not at all.
    """
    pool = await create_pool(db=db, name="ticket-pool")
    moved = await create_ticket(db=db, title="moved-before-the-crash", pool=pool)
    pending = await create_ticket(db=db, title="still-legacy", pool=pool)
    assert await rewrite_records_to_legacy_shape(db=db, node_ids=[pending.id]) == 1
    moved_before = await reservation_records(db=db, pool_id=pool.id)

    run = await run_migration(db=db)
    assert not run.result.errors
    assert not run.validation.errors
    assert "Re-anchored 1 number pool record(s) onto the attribute they belong to." in run.output
    assert "Dropped 0 number pool record(s) an attribute held beyond the newest one." in run.output

    records = await reservation_records(db=db, pool_id=pool.id)
    assert sorted((record.anchor, record.attribute_id or "") for record in records) == sorted(
        [
            ("Attribute", attribute_id_of(node=moved)),
            ("Attribute", attribute_id_of(node=pending)),
        ]
    )
    already_moved = [record for record in moved_before if record.properties["identifier"] == moved.id]
    assert [record for record in records if record.properties["identifier"] == moved.id] == already_moved
