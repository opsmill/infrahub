from __future__ import annotations

import contextlib
import heapq
import io
import os
import re
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Self

import boto3
import botocore.exceptions
import fastapi_storages

from infrahub.exceptions import NodeNotFoundError, StorageEncryptionError, StorageIntegrityError
from infrahub.log import get_logger
from infrahub.storage_encryption.crypto import has_envelope_magic, is_envelope, open_envelope, seal
from infrahub.storage_encryption.status import HEADER_PEEK_LENGTH, check_header

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from infrahub.config import StorageSettings
    from infrahub.storage_encryption.crypto import StorageKey
    from infrahub.storage_encryption.status import EncryptionCheck

log = get_logger()

S3_MISSING_OBJECT_CODES = frozenset({"404", "NoSuchKey", "NotFound"})

TEMPORARY_FILE_PREFIX = "."
TEMPORARY_FILE_SUFFIX = ".tmp"
"""A file of the local storage whose name has this prefix and this suffix is an unfinished write, not an object."""

TEMPORARY_FILE_TOKEN_LENGTH = 8
TEMPORARY_FILE_PATTERN = re.compile(
    rf"{re.escape(TEMPORARY_FILE_PREFIX)}[^/]+\.[0-9a-f]{{{2 * TEMPORARY_FILE_TOKEN_LENGTH}}}{re.escape(TEMPORARY_FILE_SUFFIX)}"
)
"""The exact name of the temporary file that replacing an object writes: the identifier and a random token."""

STALE_TEMPORARY_FILE_AGE = timedelta(hours=1)
"""A write that has not touched its temporary file for this long was interrupted, since a write takes seconds."""


@dataclass(frozen=True)
class StoredContent:
    content: bytes

    authenticated: bool
    """Whether the content was decrypted from an envelope that proved it unchanged."""


@dataclass(frozen=True)
class StoredObject:
    """One object of the storage, as a listing reports it."""

    identifier: str

    size: int
    """Size in bytes of the object as it is stored, so of the envelope when the object is encrypted."""

    last_modified: datetime
    """Time of the last write to the object, in UTC."""


@dataclass(frozen=True)
class StoredObjectListing:
    """One page of a listing and the point where the next page starts."""

    objects: list[StoredObject]
    """The objects of the page. An object deleted while the page was read is not in it, so it can hold fewer than the limit."""

    next_start_after: str | None
    """The identifier to pass as `start_after` for the next page, or None when no identifier sorts after the page."""


def _is_temporary_file(name: str) -> bool:
    return name.startswith(TEMPORARY_FILE_PREFIX) and name.endswith(TEMPORARY_FILE_SUFFIX)


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

    def iter_objects(self, start_after: str | None, limit: int | None) -> Iterator[StoredObject]:
        """Yield the objects of the bucket in the order of their keys, one listing request per page of keys.

        Raises:
            botocore.exceptions.ClientError: If the bucket cannot be listed.

        """
        objects = self._bucket.objects.filter(Marker=start_after) if start_after else self._bucket.objects.all()
        if limit is not None:
            objects = objects.limit(limit)
        for summary in objects:
            yield StoredObject(
                identifier=summary.key, size=summary.size, last_modified=summary.last_modified.astimezone(UTC)
            )

    def get_object_size(self, name: str) -> int:
        """Return the size in bytes of an object from its metadata, without downloading it.

        Raises:
            botocore.exceptions.ClientError: If the object cannot be read, for example because it does not exist.

        """
        return self._bucket.Object(name).content_length

    def get_bounded(
        self, name: str, max_size: int, before_read: Callable[[int], None] | None = None
    ) -> tuple[int, bytes | None]:
        """Return the size of an object and, when it is at most `max_size` bytes, its content, in one request.

        The size comes from the headers of the answer, so the body of a larger object is not downloaded. When
        `before_read` is given it is called with the size of an object that fits, before the body is downloaded;
        an exception it raises ends the call without downloading the body.

        Raises:
            botocore.exceptions.ClientError: If the object cannot be read, for example because it does not exist.

        """
        response = self._bucket.Object(name).get()
        body = response["Body"]
        try:
            size = int(response["ContentLength"])
            if size > max_size:
                return size, None
            if before_read is not None:
                before_read(size)
            return size, body.read()
        finally:
            body.close()

    def put(self, name: str, content: bytes) -> None:
        """Store `content` under `name` in one request, which replaces an existing object atomically.

        Raises:
            botocore.exceptions.ClientError: If the object cannot be written.

        """
        self._bucket.put_object(Key=name, Body=content, ACL=self.AWS_DEFAULT_ACL, ContentType=self.default_content_type)


fastapi_storages.InfrahubS3ObjectStorage = InfrahubS3ObjectStorage


class InfrahubObjectStorage:
    _settings: StorageSettings
    _storage: fastapi_storages.base.BaseStorage
    _key: StorageKey | None = None

    def __init__(self, settings: StorageSettings, key: StorageKey | None = None) -> None:
        """Access the configured storage driver.

        `key` opens every encrypted object read, and with encryption enabled it also seals every object written.
        Without it, reading an encrypted object raises, and so does writing one while encryption is enabled.
        """
        self._settings = settings
        self._key = key

        driver = getattr(fastapi_storages, self._settings.driver.name)

        driver_settings = getattr(self._settings, self._settings.driver.value.lower())
        self._storage = driver(**driver_settings.model_dump(by_alias=True))

    @classmethod
    async def init(cls, settings: StorageSettings, key: StorageKey | None = None) -> Self:
        return cls(settings, key=key)

    @property
    def key(self) -> StorageKey | None:
        """The key this process seals and opens stored objects with, or None when it has none."""
        return self._key

    @property
    def encryption_enabled(self) -> bool:
        """Whether every object written from now on is encrypted."""
        return self._settings.encryption_enabled

    def _active_key(self) -> StorageKey:
        if self._key is None:
            raise StorageEncryptionError(
                "Storage encryption is enabled but this process has no key; only the API server reads and "
                "writes stored objects"
            )
        return self._key

    def _key_to_open(self, identifier: str) -> StorageKey:
        if self._key is not None:
            return self._key
        if self._settings.encryption_enabled:
            return self._active_key()
        raise StorageEncryptionError(
            f"The stored object {identifier} is encrypted but this process has no key to decrypt it; set "
            "INFRAHUB_STORAGE_ENCRYPTION_KEY, or INFRAHUB_SECURITY_SECRET_KEY when no dedicated key was used, to the "
            "value that was in use when encryption was enabled"
        )

    def store(self, identifier: str, content: BinaryIO) -> None:
        if not self._settings.encryption_enabled:
            self._storage.write(content, identifier)
            return
        key = self._active_key()
        content.seek(0)
        self._storage.write(io.BytesIO(seal(identifier=identifier, content=content.read(), key=key)), identifier)

    def read_header(self, identifier: str, request_length: int = HEADER_PEEK_LENGTH) -> bytes | None:
        """Return the first bytes of a stored object, or None when no object is stored under `identifier`.

        Args:
            identifier: The storage identifier of the object.
            request_length: Bytes an S3 read asks for. The result is cut to the header whatever its value; asking
                for more only changes the request, which some S3 services answer faster.

        Raises:
            botocore.exceptions.ClientError: If the storage fails for a reason other than a missing object.

        """
        try:
            if isinstance(self._storage, InfrahubS3ObjectStorage):
                return self._storage.read_head(identifier, max(HEADER_PEEK_LENGTH, request_length))[:HEADER_PEEK_LENGTH]
            with self._storage.open(identifier) as f:
                return f.read(HEADER_PEEK_LENGTH)
        except FileNotFoundError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response.get("Error", {}).get("Code") in S3_MISSING_OBJECT_CODES:
                return None
            raise

    def inspect_encryption(self, identifier: str, request_length: int = HEADER_PEEK_LENGTH) -> EncryptionCheck:
        """Tell from its header whether a stored object is encrypted and readable with the current key.

        `request_length` is the number of bytes an S3 read asks for; the header is cut from the answer.
        """
        return check_header(
            header=self.read_header(identifier=identifier, request_length=request_length),
            key=self._key,
            encryption_enabled=self._settings.encryption_enabled,
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
        # With encryption off only a complete envelope counts, so plain files that start with the magic are served.
        is_encrypted = has_envelope_magic(stored) if self._settings.encryption_enabled else is_envelope(stored)
        if not is_encrypted:
            return StoredContent(content=stored, authenticated=False)
        key = self._key_to_open(identifier=identifier)
        try:
            content = open_envelope(identifier=identifier, content=stored, key=key)
        except StorageIntegrityError as exc:
            log.warning(
                "Refused a stored object that failed its integrity check",
                storage_id=identifier,
                reason=exc.reason,
                key_fingerprint=key.fingerprint,
            )
            raise
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

    def list_objects(self, start_after: str | None = None, limit: int | None = None) -> Iterator[StoredObject]:
        """Yield the stored objects in the ascending order of their identifiers, without holding them all in memory.

        The order is the code point order of the identifiers on both drivers, so a caller pages through the
        storage by passing the last identifier of a page as `start_after` of the next one. Objects are listed
        whether or not a node still refers to them. An object written or deleted while the listing runs may or
        may not be reported.

        Cost on the local filesystem: every call reads all the names of the storage directory once, then reads
        the size and time of an object only when it yields it. With a `limit` it keeps at most `limit` names in
        memory; without one it keeps and sorts every name after `start_after`. Unfinished writes are not listed.
        An object deleted during the scan is not yielded, so fewer objects than `limit` do not mean the end of the
        storage; a caller that pages uses `list_page`, which reports where the next page starts.

        Cost on S3: one listing request per 1000 objects yielded, and nothing is sorted or kept in memory.

        Args:
            start_after: Yield only the objects whose identifier sorts strictly after this one.
            limit: Yield at most this number of objects.

        Raises:
            ValueError: If `limit` is negative.
            NotImplementedError: If the storage driver cannot be listed.
            OSError: If the local storage directory cannot be read.
            botocore.exceptions.ClientError: If the bucket cannot be listed.

        """
        if limit is not None and limit < 0:
            raise ValueError("limit must not be negative")
        if isinstance(self._storage, InfrahubS3ObjectStorage):
            yield from self._storage.iter_objects(start_after=start_after, limit=limit)
        elif isinstance(self._storage, fastapi_storages.FileSystemStorage):
            yield from _iter_local_objects(directory=self._storage._path, start_after=start_after, limit=limit)
        else:
            raise NotImplementedError(f"The storage driver {self._settings.driver.name} cannot be listed")

    def list_page(self, start_after: str | None, limit: int) -> StoredObjectListing:
        """Return one page of at most `limit` objects in the order of their identifiers, and where the next page starts.

        The end of the storage is the absence of a next page, not a page shorter than `limit`: on the local
        filesystem an object deleted between the scan of the names and the read of its size is left out of the
        page, but the next page still starts after its name. Costs are those of `list_objects`, plus one name
        read ahead to tell whether another page follows.

        Args:
            start_after: List only the objects whose identifier sorts strictly after this one.
            limit: The most objects of a page; at least 1.

        Raises:
            ValueError: If `limit` is less than 1.
            NotImplementedError: If the storage driver cannot be listed.
            OSError: If the local storage directory cannot be read.
            botocore.exceptions.ClientError: If the bucket cannot be listed.

        """
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if isinstance(self._storage, InfrahubS3ObjectStorage):
            listed = list(self._storage.iter_objects(start_after=start_after, limit=limit + 1))
            page = listed[:limit]
            return StoredObjectListing(
                objects=page, next_start_after=page[-1].identifier if len(listed) > limit else None
            )
        if isinstance(self._storage, fastapi_storages.FileSystemStorage):
            return _list_local_page(directory=self._storage._path, start_after=start_after, limit=limit)
        raise NotImplementedError(f"The storage driver {self._settings.driver.name} cannot be listed")

    def get_size(self, identifier: str) -> int | None:
        """Return the size in bytes of a stored object without reading it, or None when no object is stored.

        The size is the one of the object as it is stored, so of the envelope when the object is encrypted.

        Raises:
            botocore.exceptions.ClientError: If the storage fails for a reason other than a missing object.

        """
        try:
            if isinstance(self._storage, InfrahubS3ObjectStorage):
                return self._storage.get_object_size(identifier)
            return self._storage.get_size(identifier)
        except FileNotFoundError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response.get("Error", {}).get("Code") in S3_MISSING_OBJECT_CODES:
                return None
            raise

    def read_stored_bounded(
        self, identifier: str, max_size: int, before_read: Callable[[int], None] | None = None
    ) -> tuple[int, bytes | None] | None:
        """Return the size of a stored object and its bytes exactly as stored, or None when no object is stored.

        The bytes are None when the object is larger than `max_size`; it is then not read. Nothing is decrypted.
        On S3 this is one request; on the local filesystem one stat and one read. `before_read` is called with
        the size of an object that fits, before its bytes are read, so a caller can claim memory for them; an
        exception it raises ends the call without reading the bytes.

        Raises:
            OSError: If the local filesystem fails for a reason other than a missing file.
            botocore.exceptions.ClientError: If S3 fails for a reason other than a missing object.

        """
        try:
            if isinstance(self._storage, InfrahubS3ObjectStorage):
                return self._storage.get_bounded(identifier, max_size, before_read)
            if isinstance(self._storage, fastapi_storages.FileSystemStorage):
                path = self._storage._path / identifier
                size = path.stat().st_size
                if size > max_size:
                    return size, None
                if before_read is not None:
                    before_read(size)
                return size, path.read_bytes()
        except FileNotFoundError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response.get("Error", {}).get("Code") in S3_MISSING_OBJECT_CODES:
                return None
            raise
        raise NotImplementedError(f"The storage driver {self._settings.driver.name} cannot read a bounded object")

    def replace(self, identifier: str, content: bytes) -> None:
        """Overwrite a stored object with `content` exactly as given: nothing is encrypted here.

        A reader sees either the previous object or the new one, never a part of it, and an interrupted call
        leaves the previous object in place. On the local filesystem the content is written to a temporary
        file of the same directory, synced to disk, then renamed over the object. On S3 it is one request.

        The local filesystem refuses an identifier that has no object. S3 cannot refuse it in the same request,
        so there the object is created.

        Raises:
            NodeNotFoundError: If the local filesystem has no object under `identifier`.
            NotImplementedError: If the storage driver cannot replace an object.
            OSError: If the local filesystem fails; the previous object is then still in place.
            botocore.exceptions.ClientError: If S3 refuses the write; the previous object is then still in place.

        """
        if isinstance(self._storage, InfrahubS3ObjectStorage):
            self._storage.put(identifier, content)
        elif isinstance(self._storage, fastapi_storages.FileSystemStorage):
            _replace_local_object(directory=self._storage._path, identifier=identifier, content=content)
        else:
            raise NotImplementedError(f"The storage driver {self._settings.driver.name} cannot replace an object")

    def remove_stale_temporary_files(self, older_than: timedelta = STALE_TEMPORARY_FILE_AGE) -> list[str]:
        """Delete the temporary files that an interrupted replacement left in the local storage, and return their names.

        Only a regular file whose name is exactly that of a temporary file and which was last written more than
        `older_than` ago is deleted, so a file of a write in progress and every stored object are kept. S3 writes
        an object in one request and leaves no temporary file, so there this does nothing.

        Raises:
            OSError: If the local storage directory cannot be read.

        """
        if not isinstance(self._storage, fastapi_storages.FileSystemStorage):
            return []
        removed = _remove_stale_local_temporary_files(directory=self._storage._path, older_than=older_than)
        if removed:
            log.warning("Removed temporary files of interrupted replacements from the storage", files=removed)
        return removed


def _remove_stale_local_temporary_files(directory: Path, older_than: timedelta) -> list[str]:
    oldest_kept = time.time() - older_than.total_seconds()
    removed: list[str] = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if not TEMPORARY_FILE_PATTERN.fullmatch(entry.name) or not entry.is_file(follow_symlinks=False):
                continue
            try:
                if entry.stat(follow_symlinks=False).st_mtime >= oldest_kept:
                    continue
                Path(entry.path).unlink()
            except FileNotFoundError:
                continue
            removed.append(entry.name)
    return sorted(removed)


def _iter_local_object_names(directory: Path, start_after: str | None) -> Iterator[str]:
    with os.scandir(directory) as entries:
        for entry in entries:
            if start_after is not None and entry.name <= start_after:
                continue
            if _is_temporary_file(entry.name) or not entry.is_file(follow_symlinks=False):
                continue
            yield entry.name


def _stat_local_objects(directory: Path, names: list[str]) -> Iterator[StoredObject]:
    for name in names:
        try:
            stat = (directory / name).stat()
        except FileNotFoundError:
            continue
        yield StoredObject(
            identifier=name, size=stat.st_size, last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        )


def _iter_local_objects(directory: Path, start_after: str | None, limit: int | None) -> Iterator[StoredObject]:
    names = _iter_local_object_names(directory=directory, start_after=start_after)
    yield from _stat_local_objects(
        directory=directory, names=sorted(names) if limit is None else heapq.nsmallest(limit, names)
    )


def _list_local_page(directory: Path, start_after: str | None, limit: int) -> StoredObjectListing:
    # One name more than the page tells whether another page follows; the cursor is a scanned name, not a listed one.
    names = heapq.nsmallest(limit + 1, _iter_local_object_names(directory=directory, start_after=start_after))
    scanned = names[:limit]
    return StoredObjectListing(
        objects=list(_stat_local_objects(directory=directory, names=scanned)),
        next_start_after=scanned[-1] if len(names) > limit else None,
    )


def _replace_local_object(directory: Path, identifier: str, content: bytes) -> None:
    target = directory / identifier
    if not target.is_file():
        raise NodeNotFoundError(node_type="StorageObject", identifier=identifier)
    temporary = (
        directory
        / f"{TEMPORARY_FILE_PREFIX}{identifier}.{secrets.token_hex(TEMPORARY_FILE_TOKEN_LENGTH)}{TEMPORARY_FILE_SUFFIX}"
    )
    try:
        with temporary.open("xb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    # The rename is durable only once the directory entry is on disk.
    directory_fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
