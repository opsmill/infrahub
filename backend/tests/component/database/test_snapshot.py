from pathlib import Path

from infrahub.core import registry
from infrahub.core.initialization import initialization
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.database.snapshot import (
    capture_graph,
    deterministic_generation,
    read_snapshot_file,
    restore_graph,
)

COMMITTED_SNAPSHOT = Path(__file__).parents[2] / "fixtures" / "db_snapshots" / "core_bootstrap.json.gz"
REGENERATE_HINT = (
    "The committed database snapshot is stale. Regenerate it against an empty database with:\n"
    "  infrahub db snapshot-dump backend/tests/fixtures/db_snapshots/core_bootstrap.json.gz"
)


async def test_committed_snapshot_is_fresh(db: InfrahubDatabase, local_storage_dir: Path) -> None:
    """The committed snapshot must equal a freshly, deterministically generated one.

    This is the freshness gate: when the core schema, default menu, roles/permissions or graph
    version change, a fresh bootstrap diverges from the committed snapshot and this test fails,
    signalling that the snapshot must be regenerated and committed.
    """
    await delete_all_nodes(db=db)
    registry.delete_all()

    with deterministic_generation():
        await initialization(db=db, add_database_indexes=True)
    fresh = await capture_graph(db=db)

    committed = read_snapshot_file(str(COMMITTED_SNAPSHOT))
    assert fresh.graph_version == committed.graph_version, REGENERATE_HINT
    assert fresh.to_dict() == committed.to_dict(), REGENERATE_HINT


async def test_snapshot_restore_round_trip(db: InfrahubDatabase, local_storage_dir: Path) -> None:
    """Restoring the committed snapshot yields a database that skips first-time initialization."""
    await delete_all_nodes(db=db)
    registry.delete_all()

    snapshot = read_snapshot_file(str(COMMITTED_SNAPSHOT))
    await restore_graph(db=db, snapshot=snapshot)

    node_count = (await db.execute_query(query="MATCH (n) RETURN count(n) AS count"))[0].get("count")
    edge_count = (await db.execute_query(query="MATCH ()-[r]->() RETURN count(r) AS count"))[0].get("count")
    assert node_count == len(snapshot.nodes)
    assert edge_count == len(snapshot.edges)
    # No leftover restore scaffolding remains on the graph.
    leftover = (await db.execute_query(query="MATCH (n:`_SnapshotNode`) RETURN count(n) AS count"))[0].get("count")
    assert leftover == 0

    registry.delete_all()
    is_initial_setup = await initialization(db=db, add_database_indexes=True)
    assert is_initial_setup is False
