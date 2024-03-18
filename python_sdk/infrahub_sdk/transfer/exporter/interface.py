from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional


class ExporterInterface(ABC):
    @abstractmethod
    async def export(
        self, export_directory: Path, namespaces: List[str], branch: str, exclude: Optional[List[str]] = None
    ) -> None: ...
