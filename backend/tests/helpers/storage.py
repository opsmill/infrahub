from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import os


def vanishing_directory(path: Path, vanishing: frozenset[str]) -> Path:
    """Return a directory whose files named in `vanishing` are listed by a scan but gone when their size is read."""

    class VanishingDirectory(Path):
        def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
            if self.name in vanishing:
                raise FileNotFoundError(self.name)
            return super().stat(follow_symlinks=follow_symlinks)

    return VanishingDirectory(path)
