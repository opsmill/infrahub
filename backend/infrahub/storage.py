from __future__ import annotations

import contextlib
import io
from typing import TYPE_CHECKING, Any, BinaryIO

import botocore.exceptions
import fastapi_storages
from typing_extensions import Self

from infrahub.exceptions import NodeNotFoundError

if TYPE_CHECKING:
    from infrahub.config import StorageSettings


class InfrahubS3ObjectStorage(fastapi_storages.S3Storage):
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        super().__init__()

    def open(self, name: str) -> BinaryIO:
        f = io.BytesIO()
        self._bucket.download_fileobj(name, f)
        f.flush()
        f.seek(0)
        return f  # type: ignore

    def delete(self, name: str) -> None:
        self._bucket.Object(name).delete()


fastapi_storages.InfrahubS3ObjectStorage = InfrahubS3ObjectStorage


class InfrahubObjectStorage:
    _settings: StorageSettings
    _storage: fastapi_storages.base.BaseStorage

    def __init__(self, settings: StorageSettings) -> None:
        self._settings = settings

        driver = getattr(fastapi_storages, self._settings.driver.name)

        driver_settings = getattr(self._settings, self._settings.driver.value.lower())
        self._storage = driver(**driver_settings.model_dump(by_alias=True))

    @classmethod
    async def init(cls, settings: StorageSettings) -> Self:
        return cls(settings)

    def store(self, identifier: str, content: BinaryIO) -> None:
        self._storage.write(content, identifier)

    def retrieve(self, identifier: str) -> str:
        try:
            with self._storage.open(identifier) as f:
                return f.read().decode()
        except (FileNotFoundError, botocore.exceptions.ClientError) as err:
            raise NodeNotFoundError(node_type="StorageObject", identifier=identifier) from err

    def delete(self, identifier: str) -> None:
        """Delete a file from storage.

        Args:
            identifier: The storage identifier of the file to delete.

        Note:
            Silently ignores if the file does not exist.
        """
        if isinstance(self._storage, fastapi_storages.FileSystemStorage):
            (self._storage._path / identifier).unlink(missing_ok=True)
        else:
            with contextlib.suppress(FileNotFoundError, botocore.exceptions.ClientError):
                self._storage.delete(identifier)
