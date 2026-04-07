from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.migrations.graph import MIGRATIONS


def test_graph_version_matches_migration_count() -> None:
    assert len(MIGRATIONS) == GRAPH_VERSION, (
        f"GRAPH_VERSION ({GRAPH_VERSION}) must equal to the number of migrations "
        f"({len(MIGRATIONS)}). Update GRAPH_VERSION or add/remove a migration."
    )


def test_last_migration_minimum_version() -> None:
    last = MIGRATIONS[-1].init()
    assert last.minimum_version == GRAPH_VERSION - 1, (
        f"Last migration minimum_version ({last.minimum_version}) must be GRAPH_VERSION - 1 ({GRAPH_VERSION - 1})."
    )


def test_no_duplicate_migration_minimum_versions() -> None:
    minimum_versions = [m.init().minimum_version for m in MIGRATIONS]
    duplicate_versions = [v for v in minimum_versions if minimum_versions.count(v) > 1]
    assert not duplicate_versions, f"Duplicate minimum_version values found: {sorted(set(duplicate_versions))}"
