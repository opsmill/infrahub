from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.migrations.shared import BaseMigration

MIGRATION_FILE_PATTERN = re.compile(r"^m(\d{3})_.+\.py$")
MIGRATION_PACKAGE_PATTERN = re.compile(r"^m(\d{3})_[^.]+$")


def discover_migrations() -> list[type[BaseMigration]]:
    """Scan the graph migrations directory for migrations and return sorted migration classes.

    Discovers modules matching ``m{NNN}_{name}.py`` and packages matching
    ``m{NNN}_{name}/`` (whose ``__init__.py`` must export the migration class),
    imports each, extracts the ``Migration{NNN}`` class, validates there are no
    duplicate numbers, and returns the list sorted by migration number.

    Raises:
        ImportError: If a migration module is missing its expected ``Migration{NNN}``
            class, or if two migrations share the same number.

    """
    migration_dir = Path(__file__).parent
    migrations: list[tuple[int, type[BaseMigration]]] = []

    for path in sorted(migration_dir.iterdir()):
        if path.is_file():
            match = MIGRATION_FILE_PATTERN.match(path.name)
        elif (path / "__init__.py").is_file():
            match = MIGRATION_PACKAGE_PATTERN.match(path.name)
        else:
            match = None
        if not match:
            continue
        number = int(match.group(1))
        module = importlib.import_module(f".{path.stem}", package=__package__)
        class_name = f"Migration{number:03d}"
        migration_class = getattr(module, class_name, None)
        if migration_class is None:
            raise ImportError(f"{path.name} does not contain expected class {class_name}")
        migrations.append((number, migration_class))

    # Validate no duplicate numbers
    seen: dict[int, type[BaseMigration]] = {}
    for num, cls in migrations:
        if num in seen:
            raise ImportError(f"Duplicate migration number {num:03d}: {seen[num].__name__} and {cls.__name__}")
        seen[num] = cls

    return [cls for _, cls in migrations]
