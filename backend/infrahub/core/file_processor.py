from __future__ import annotations

import contextlib
import hashlib
import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

import puremagic
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core import registry
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from starlette.datastructures import UploadFile


@dataclass
class FileUploadResult:
    storage_id: str
    file_name: str
    checksum: str
    file_size: int
    file_type: str


class FileUploadProcessor:
    """Processor for handling file uploads."""

    def __init__(self, file: UploadFile) -> None:
        self.file = file
        self.storage_id: str | None = None

    def _get_file_size(self) -> int:
        """Get the size of the uploaded file without loading it into memory.

        Returns:
            The file size in bytes.
        """
        # Access underlying file object which supports seek with whence parameter
        # Starlette's UploadFile.seek() only accepts offset, not whence
        self.file.file.seek(0, io.SEEK_END)
        size = self.file.file.tell()
        self.file.file.seek(0)
        return size

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Format a file size in bytes to a human-readable string.

        Args:
            size_bytes: The file size in bytes.

        Returns:
            A human-readable string like "1.5 MB" or "256 KB".
        """
        value = float(size_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(value) < 1024:
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
            value /= 1024
        return f"{value:.1f} PB"

    @staticmethod
    def _detect_mime_type(content: bytes) -> str:
        """Detect the MIME type of a file using magic bytes.

        Falls back to `application/octet-stream` if the type cannot be determined.

        Args:
            content: The file content (or first few KB) as bytes.

        Returns:
            The detected MIME type string.
        """
        with contextlib.suppress(puremagic.PureError):
            results = puremagic.magic_string(content)
            if results:
                return results[0].mime_type

        return "application/octet-stream"

    async def _compute_checksum(self) -> str:
        """Compute SHA-1 checksum of the file using chunked reading.

        Reads the file in 64KB chunks to avoid loading large files entirely into memory.

        Returns:
            The checksum as a hex string.
        """
        await self.file.seek(0)
        hasher = hashlib.sha1(usedforsecurity=False)

        while chunk := await self.file.read(65536):
            hasher.update(chunk)

        return hasher.hexdigest()

    async def process(self) -> FileUploadResult:
        """Process the file upload and store it in the storage backend.

        Returns:
            FileUploadResult containing all file metadata.

        Raises:
            ValidationError: If the file exceeds the maximum allowed size.
        """
        file_size = self._get_file_size()
        if file_size > config.SETTINGS.storage.max_file_size * 1024 * 1024:
            raise ValidationError(
                f"File size ({self._format_file_size(size_bytes=file_size)}) exceeds maximum allowed size "
                f"({config.SETTINGS.storage.max_file_size} MB)"
            )

        magic_bytes = await self.file.read(2048)
        file_type = self._detect_mime_type(content=magic_bytes)
        checksum = await self._compute_checksum()
        self.storage_id = str(UUIDT())
        file_name = self.file.filename or self.storage_id

        await self.file.seek(0)
        registry.storage.store(identifier=self.storage_id, content=self.file.file)

        return FileUploadResult(
            storage_id=self.storage_id, file_name=file_name, checksum=checksum, file_size=file_size, file_type=file_type
        )

    def delete_file(self) -> None:
        """Delete the uploaded file from the storage backend."""
        if self.storage_id:
            registry.storage.delete(identifier=self.storage_id)
