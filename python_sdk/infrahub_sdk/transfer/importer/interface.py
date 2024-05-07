from abc import ABC, abstractmethod
from pathlib import Path


class ImporterInterface(ABC):
    @abstractmethod
    async def import_data(self, import_directory: Path, branch: str) -> None: ...
