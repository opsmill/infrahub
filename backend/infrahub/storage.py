from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, BinaryIO

import boto3
import botocore.exceptions
import fastapi_storages
from typing_extensions import Self

from infrahub.exceptions import NodeNotFoundError, StorageEncryptionError
from infrahub.storage_encryption.crypto import is_envelope, open_envelope, seal

if TYPE_CHECKING:
    from infrahub.config import StorageSettings
    from infrahub.storage_encryption.crypto import StorageKey


@dataclass(frozen=True)
class StoredContent:
    content: bytes

    authenticated: bool
    """Whether the content was decrypted from an envelope that proved it unchanged."""


class InfrahubS3ObjectStorage(fastapi_storages.S3Storage):
    AWS_CA_BUNDLE: str | None = None
    """Path to a CA bundle used to verify the S3 endpoint certificate; None keeps boto3's default trust store."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        access_key = str(kwargs.get("AWS_ACCESS_KEY_ID") or "").strip()
        secret_key = str(kwargs.get("AWS_SECRET_ACCESS_KEY") or "").strip()
        if bool(access_key) != bool(secret_key):
            raise ValueError(
                "S3 storage requires both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, or neither. "
                "Set both to use static credentials, or leave both unset to use the default AWS "
                "credential provider chain (IRSA, EC2 instance profiles, ECS task roles)."
            )
        if not access_key:
            # No static credentials configured. fastapi_storages.S3Storage types these as str and
            # forwards them to boto3, which sends an empty string verbatim instead of falling back
            # to the default AWS credential provider chain. Set them to None so boto3 resolves
            # credentials from the environment (IRSA, EC2 instance profiles, ECS task roles).
            self.AWS_ACCESS_KEY_ID = None  # type: ignore[assignment]
            self.AWS_SECRET_ACCESS_KEY = None  # type: ignore[assignment]

        # Mirrors fastapi_storages.S3Storage.__init__, which offers no hook to pass a CA bundle to boto3.
        if self.AWS_S3_ENDPOINT_URL.startswith("http"):
            raise ValueError("AWS_S3_ENDPOINT_URL should not contain the protocol")
        self._http_scheme = "https" if self.AWS_S3_USE_SSL else "http"
        self._url = f"{self._http_scheme}://{self.AWS_S3_ENDPOINT_URL}"
        self._s3 = boto3.resource(
            "s3",
            endpoint_url=self._url,
            use_ssl=self.AWS_S3_USE_SSL,
            verify=self.AWS_CA_BUNDLE or None,
            aws_access_key_id=self.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
        )
        self._bucket = self._s3.Bucket(name=self.AWS_S3_BUCKET_NAME)

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
    _key: StorageKey | None = None

    def __init__(self, settings: StorageSettings, key: StorageKey | None = None) -> None:
        """Access the configured storage driver.

        With encryption enabled, `key` seals every object written and opens every encrypted object read;
        without it, writing an object or reading an encrypted one raises.
        """
        self._settings = settings
        self._key = key

        driver = getattr(fastapi_storages, self._settings.driver.name)

        driver_settings = getattr(self._settings, self._settings.driver.value.lower())
        self._storage = driver(**driver_settings.model_dump(by_alias=True))

    @classmethod
    async def init(cls, settings: StorageSettings, key: StorageKey | None = None) -> Self:
        return cls(settings, key=key)

    def _active_key(self) -> StorageKey:
        if self._key is None:
            raise StorageEncryptionError(
                "Storage encryption is enabled but this process has no key; only the API server reads and "
                "writes stored objects"
            )
        return self._key

    def store(self, identifier: str, content: BinaryIO) -> None:
        if not self._settings.encryption_enabled:
            self._storage.write(content, identifier)
            return
        key = self._active_key()
        content.seek(0)
        self._storage.write(io.BytesIO(seal(identifier=identifier, content=content.read(), key=key)), identifier)

    def retrieve(self, identifier: str) -> str:
        return self.retrieve_binary(identifier=identifier).decode()

    def retrieve_binary(self, identifier: str) -> bytes:
        return self.read(identifier=identifier).content

    def read(self, identifier: str) -> StoredContent:
        """Return the content of a stored object, decrypted when it is encrypted and encryption is enabled.

        An object stored before encryption was enabled is returned as it is, not authenticated.

        Raises:
            NodeNotFoundError: If no object is stored under `identifier`.
            StorageIntegrityError: If an encrypted object uses another key or fails authentication.

        """
        try:
            with self._storage.open(identifier) as f:
                stored = f.read()
        except (FileNotFoundError, botocore.exceptions.ClientError) as err:
            raise NodeNotFoundError(node_type="StorageObject", identifier=identifier) from err
        if not self._settings.encryption_enabled or not is_envelope(stored):
            return StoredContent(content=stored, authenticated=False)
        content = open_envelope(identifier=identifier, content=stored, key=self._active_key())
        return StoredContent(content=content, authenticated=True)

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
