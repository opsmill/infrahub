from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.migrations.graph import MIGRATIONS


def test_graph_version_matches_migration_count() -> None:
    last = MIGRATIONS[-1].init()
    assert last.number == GRAPH_VERSION, (
        f"GRAPH_VERSION ({GRAPH_VERSION}) must equal to the number of migrations "
        f"({last.number}). Update GRAPH_VERSION or add/remove a migration."
    )


def test_last_migration_minimum_version() -> None:
    last = MIGRATIONS[-1].init()
    assert last.minimum_version == GRAPH_VERSION - 1, (
        f"Last migration minimum_version ({last.minimum_version}) must be GRAPH_VERSION - 1 ({GRAPH_VERSION - 1})."
    )


def test_no_duplicate_migration_minimum_versions_and_number() -> None:
    minimum_versions = [(m.init().minimum_version, m.init().number) for m in MIGRATIONS]
    duplicate_versions = [(v, n) for v, n in minimum_versions if minimum_versions.count((v, n)) > 1]
    assert not duplicate_versions, (
        f"Duplicate minimum_version and number values found: {sorted(set(duplicate_versions))}"
    )
