from __future__ import annotations

from infrahub.core.migrations.graph.discovery import MIGRATION_FILE_PATTERN, discover_migrations


class TestMigrationFilePattern:
    def test_valid_pattern(self) -> None:
        assert MIGRATION_FILE_PATTERN.match("m001_add_version.py")
        assert MIGRATION_FILE_PATTERN.match("m067_freeze_orphaned.py")
        assert MIGRATION_FILE_PATTERN.match("m123_some_migration.py")

    def test_invalid_pattern(self) -> None:
        assert not MIGRATION_FILE_PATTERN.match("m01_too_short.py")
        assert not MIGRATION_FILE_PATTERN.match("m1234_too_long.py")
        assert not MIGRATION_FILE_PATTERN.match("migration_001.py")
        assert not MIGRATION_FILE_PATTERN.match("m001_example.txt")
        assert not MIGRATION_FILE_PATTERN.match("__init__.py")
        assert not MIGRATION_FILE_PATTERN.match("discovery.py")


class TestDiscoverMigrations:
    def test_discovers_all_migrations(self) -> None:
        migrations = discover_migrations()
        assert len(migrations) >= 1

    def test_sorted_order(self) -> None:
        migrations = discover_migrations()
        for i in range(len(migrations) - 1):
            current = migrations[i].init()
            next_one = migrations[i + 1].init()
            assert current.minimum_version <= next_one.minimum_version, (
                f"{migrations[i].__name__} (min_version={current.minimum_version}) "
                f"should come before {migrations[i + 1].__name__} (min_version={next_one.minimum_version})"
            )

    def test_first_and_last(self) -> None:
        migrations = discover_migrations()
        assert migrations[0].__name__ == "Migration001"
        # Last migration class name should match the highest-numbered file
        last_number = int(migrations[-1].__name__[len("Migration") :])
        assert last_number == len(migrations)

    def test_no_duplicate_numbers(self) -> None:
        migrations = discover_migrations()
        names = [cls.__name__ for cls in migrations]
        assert len(names) == len(set(names))

    def test_class_names_follow_convention(self) -> None:
        migrations = discover_migrations()
        for cls in migrations:
            assert cls.__name__.startswith("Migration")
            number_part = cls.__name__[len("Migration") :]
            assert len(number_part) == 3
            assert number_part.isdigit()
