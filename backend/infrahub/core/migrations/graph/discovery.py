from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.migrations.shared import MigrationTypes

MIGRATION_FILE_PATTERN = re.compile(r"^m(\d{3})_.+\.py$")


def discover_migrations() -> list[type[MigrationTypes]]:
    """Scan the graph migrations directory for migration files and return sorted migration classes.

    Discovers files matching ``m{NNN}_{name}.py``, imports each module, extracts
    the ``Migration{NNN}`` class, validates there are no duplicate numbers, and
    returns the list sorted by migration number.
    """
    migration_dir = Path(__file__).parent
    migrations: list[tuple[int, type[MigrationTypes]]] = []

    for path in sorted(migration_dir.iterdir()):
        match = MIGRATION_FILE_PATTERN.match(path.name)
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
    seen: dict[int, type[MigrationTypes]] = {}
    for num, cls in migrations:
        if num in seen:
            raise ImportError(f"Duplicate migration number {num:03d}: {seen[num].__name__} and {cls.__name__}")
        seen[num] = cls

    return [cls for _, cls in migrations]
