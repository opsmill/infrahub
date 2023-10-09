import os
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseSettings

from .main import InfrahubObjectStorage


class LocalStorageSettings(BaseSettings):
    directory: str = "storage"

    class Config:
        env_prefix = "INFRAHUB_STORAGE_LOCAL_"
        case_sensitive = False


class InfrahubLocalStorage(InfrahubObjectStorage):
    settings: LocalStorageSettings

    def __init__(self, settings: Optional[Union[dict, LocalStorageSettings]] = None) -> None:
        if isinstance(settings, LocalStorageSettings):
            self.settings = settings
        elif isinstance(settings, dict):
            self.settings = LocalStorageSettings(**settings)
        else:
            self.settings = LocalStorageSettings()

        if not os.path.isdir(self.directory_root):
            raise ValueError(
                f"A valid directory must be provided for InfrahubLocalStorage, instead of {self.directory_root}"
            )

    async def store(self, identifier: str, content: bytes) -> None:
        fileh = Path(self.generate_path(identifier=identifier))
        fileh.write_bytes(data=content)

    async def retrieve(self, identifier: str, encoding: str = "utf-8") -> str:
        fileh = Path(self.generate_path(identifier=identifier))
        return fileh.read_text(encoding=encoding)

    @property
    def directory_root(self) -> str:
        """Return the path to the root directory for the storage."""
        current_dir = os.getcwd()
        storage_directory = self.settings.directory
        if not os.path.isabs(storage_directory):
            storage_directory = os.path.join(current_dir, self.settings.directory)

        return storage_directory

    def generate_path(self, identifier: str) -> str:
        return os.path.join(self.directory_root, identifier)
