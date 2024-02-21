from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class ExporterInterface(ABC):
    @abstractmethod
    async def export(self, export_directory: Path, namespaces: List[str], branch: str) -> None:
        ...
