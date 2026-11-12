from __future__ import annotations

import contextlib
import io
from typing import TYPE_CHECKING, Any, BinaryIO, Self

import boto3
import botocore.exceptions
import fastapi_storages

from infrahub.exceptions import NodeNotFoundError
from infrahub.storage_encryption.status import HEADER_PEEK_LENGTH, check_header

if TYPE_CHECKING:
    from infrahub.config import StorageSettings
    from infrahub.storage_encryption.codec import StoredContent, StoredContentCodec
    from infrahub.storage_encryption.status import EncryptionCheck

S3_MISSING_OBJECT_CODES = frozenset({"404", "NoSuchKey", "NotFound"})


class InfrahubS3ObjectStorage(fastapi_storages.S3Storage):
    AWS_CA_BUNDLE: str | None = None
    """Path to a CA bundle used to verify the S3 endpoint certificate; None keeps boto3's default trust store."""
    AWS_S3_TLS_INSECURE: bool = False
    """Skip certificate validation of the S3 endpoint, ignoring ``AWS_CA_BUNDLE``."""

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
            self.AWS_ACCESS_KEY_ID = None
            self.AWS_SECRET_ACCESS_KEY = None

        # Mirrors fastapi_storages.S3Storage.__init__, which offers no hook to pass a CA bundle to boto3.
        if self.AWS_S3_ENDPOINT_URL.startswith("http"):
            raise ValueError("AWS_S3_ENDPOINT_URL should not contain the protocol")
        self._http_scheme = "https" if self.AWS_S3_USE_SSL else "http"
        self._url = f"{self._http_scheme}://{self.AWS_S3_ENDPOINT_URL}"
        self._s3 = boto3.resource(
            "s3",
            endpoint_url=self._url,
            use_ssl=self.AWS_S3_USE_SSL,
            verify=False if self.AWS_S3_TLS_INSECURE else (self.AWS_CA_BUNDLE or None),
            aws_access_key_id=self.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
        )
        self._bucket = self._s3.Bucket(name=self.AWS_S3_BUCKET_NAME)

    def open(self, name: str) -> BinaryIO:
        f = io.BytesIO()
        self._bucket.download_fileobj(name, f)
        f.flush()
        f.seek(0)
        return f

    def read_head(self, name: str, length: int) -> bytes:
        """Read the first `length` bytes of an object without downloading the rest.

        Raises:
            botocore.exceptions.ClientError: If the object cannot be read, for example because it does not exist.

        """
        try:
            return self._bucket.Object(name).get(Range=f"bytes=0-{length - 1}")["Body"].read()
        except botocore.exceptions.ClientError as err:
            if err.response.get("Error", {}).get("Code") == "InvalidRange":
                return b""
            raise

    def delete(self, name: str) -> None:
        self._bucket.Object(name).delete()


fastapi_storages.InfrahubS3ObjectStorage = InfrahubS3ObjectStorage


class InfrahubObjectStorage:
    _settings: StorageSettings
    _storage: fastapi_storages.base.BaseStorage
    _codec: StoredContentCodec

    def __init__(self, settings: StorageSettings, codec: StoredContentCodec) -> None:
        """Access the configured storage driver.

        The `codec` decides what is written for the content stored and what a stored object stands for, so the
        encryption of the objects is not handled here.
        """
        self._settings = settings
        self._codec = codec

        driver = getattr(fastapi_storages, self._settings.driver.name)

        driver_settings = getattr(self._settings, self._settings.driver.value.lower())
        self._storage = driver(**driver_settings.model_dump(by_alias=True))

    @classmethod
    async def init(cls, settings: StorageSettings, codec: StoredContentCodec) -> Self:
        return cls(settings, codec=codec)

    def store(self, identifier: str, content: BinaryIO) -> None:
        self._storage.write(self._codec.encode(identifier=identifier, content=content), identifier)

    def read_header(self, identifier: str) -> bytes | None:
        """Return the first bytes of a stored object, or None when no object is stored under `identifier`.

        Raises:
            botocore.exceptions.ClientError: If the storage fails for a reason other than a missing object.

        """
        try:
            if isinstance(self._storage, InfrahubS3ObjectStorage):
                return self._storage.read_head(identifier, HEADER_PEEK_LENGTH)
            with self._storage.open(identifier) as f:
                return f.read(HEADER_PEEK_LENGTH)
        except FileNotFoundError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response.get("Error", {}).get("Code") in S3_MISSING_OBJECT_CODES:
                return None
            raise

    def inspect_encryption(self, identifier: str) -> EncryptionCheck:
        """Tell from its header whether a stored object is encrypted and readable with the current key."""
        return check_header(
            header=self.read_header(identifier=identifier),
            key=self._codec.key,
            encryption_enabled=self._codec.encryption_enabled,
        )

    def retrieve(self, identifier: str) -> str:
        return self.retrieve_binary(identifier=identifier).decode()

    def retrieve_binary(self, identifier: str) -> bytes:
        return self.read(identifier=identifier).content

    def read(self, identifier: str) -> StoredContent:
        """Return the content of a stored object, decrypted when it is encrypted.

        An encrypted object is decrypted whether or not encryption is still enabled, so turning it off leaves
        earlier files readable. An object that was never encrypted is returned as it is, not authenticated.

        Raises:
            NodeNotFoundError: If no object is stored under `identifier`.
            StorageIntegrityError: If an encrypted object is truncated, uses another key or fails authentication.
            StorageEncryptionError: If the object is encrypted and this process has no key to decrypt it.

        """
        try:
            with self._storage.open(identifier) as f:
                stored = f.read()
        except (FileNotFoundError, botocore.exceptions.ClientError) as err:
            raise NodeNotFoundError(node_type="StorageObject", identifier=identifier) from err
        return self._codec.decode(identifier=identifier, stored=stored)

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
