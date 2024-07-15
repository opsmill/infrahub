from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class ExporterInterface(ABC):
    @abstractmethod
    async def export(
        self, export_directory: Path, namespaces: list[str], branch: str, exclude: Optional[list[str]] = None
    ) -> None: ...
