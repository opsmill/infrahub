import hashlib
from dataclasses import dataclass
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from starlette.datastructures import UploadFile

from infrahub.core.file_processor import FileUploadProcessor, FileUploadResult
from infrahub.exceptions import ValidationError


def create_upload_file(content: bytes, filename: str | None = "test.bin") -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename)


@dataclass
class TestUploadedFile:
    content: bytes
    filename: str
    file: UploadFile


@pytest.fixture
def upload_file() -> TestUploadedFile:
    content = b"%PDF-1.4 test content"
    filename = "test.pdf"
    return TestUploadedFile(
        content=content, filename=filename, file=create_upload_file(content=content, filename=filename)
    )


@pytest.fixture
def mock_storage() -> MagicMock:
    return MagicMock()


async def test_processor_returns_file_result(upload_file: TestUploadedFile, mock_storage: MagicMock) -> None:
    """Test that FileUploadProcessor.process returns correct FileUploadResult."""
    with (
        patch("infrahub.core.file_processor.registry") as mock_registry,
        patch("infrahub.core.file_processor.config") as mock_config,
    ):
        mock_registry.storage = mock_storage
        mock_config.SETTINGS.storage.max_file_size = 50

        processor = FileUploadProcessor(file=upload_file.file)
        result = await processor.process()

        assert isinstance(result, FileUploadResult)
        assert result.file_name == upload_file.filename
        assert result.file_size == len(upload_file.content)
        assert result.checksum
        assert result.storage_id
        mock_storage.store.assert_called_once()


async def test_processor_calculates_sha1_checksum(upload_file: TestUploadedFile, mock_storage: MagicMock) -> None:
    """Test that SHA-1 checksum is calculated correctly."""
    expected_checksum = hashlib.sha1(upload_file.content, usedforsecurity=False).hexdigest()

    with (
        patch("infrahub.core.file_processor.registry") as mock_registry,
        patch("infrahub.core.file_processor.config") as mock_config,
    ):
        mock_registry.storage = mock_storage
        mock_config.SETTINGS.storage.max_file_size = 50

        processor = FileUploadProcessor(file=upload_file.file)
        result = await processor.process()

        assert result.checksum == expected_checksum


async def test_processor_detects_mime_type(mock_storage: MagicMock) -> None:
    """Test that MIME type is detected using magic bytes."""
    png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    upload_file = create_upload_file(content=png_content, filename="image.png")

    with (
        patch("infrahub.core.file_processor.registry") as mock_registry,
        patch("infrahub.core.file_processor.config") as mock_config,
    ):
        mock_registry.storage = mock_storage
        mock_config.SETTINGS.storage.max_file_size = 50

        processor = FileUploadProcessor(file=upload_file)
        result = await processor.process()

        assert result.file_type == "image/png"


async def test_processor_fallback_mime_type(mock_storage: MagicMock) -> None:
    """Test that unknown content falls back to application/octet-stream."""
    upload_file = create_upload_file(content=b"\x00\x01\x02\x03", filename="unknown.bin")

    with (
        patch("infrahub.core.file_processor.registry") as mock_registry,
        patch("infrahub.core.file_processor.config") as mock_config,
    ):
        mock_registry.storage = mock_storage
        mock_config.SETTINGS.storage.max_file_size = 50

        processor = FileUploadProcessor(file=upload_file)
        result = await processor.process()

        assert result.file_type == "application/octet-stream"


async def test_processor_exceeds_max_size(mock_storage: MagicMock) -> None:
    """Test that files exceeding max_file_size raise ValidationError with human-readable size."""
    large_content = b"x" * (2**21)
    upload_file = create_upload_file(content=large_content, filename="large_file.bin")

    with (
        patch("infrahub.core.file_processor.registry") as mock_registry,
        patch("infrahub.core.file_processor.config") as mock_config,
    ):
        mock_registry.storage = mock_storage
        mock_config.SETTINGS.storage.max_file_size = 1

        processor = FileUploadProcessor(file=upload_file)
        with pytest.raises(ValidationError, match=r"File size \(2\.0 MB\) exceeds maximum allowed size \(1 MB\)"):
            await processor.process()

        mock_storage.store.assert_not_called()


async def test_processor_stores_file(upload_file: TestUploadedFile, mock_storage: MagicMock) -> None:
    """Test that file is stored in storage backend with correct identifier."""
    with (
        patch("infrahub.core.file_processor.registry") as mock_registry,
        patch("infrahub.core.file_processor.config") as mock_config,
    ):
        mock_registry.storage = mock_storage
        mock_config.SETTINGS.storage.max_file_size = 50

        processor = FileUploadProcessor(file=upload_file.file)
        result = await processor.process()

        mock_storage.store.assert_called_once()
        call_kwargs = mock_storage.store.call_args.kwargs
        assert call_kwargs["identifier"] == result.storage_id
        assert call_kwargs["content"] == b"%PDF-1.4 test content"


async def test_processor_unnamed_file(mock_storage: MagicMock) -> None:
    """Test that files without filename use storage_id as file_name."""
    upload_file = create_upload_file(content=b"content", filename=None)

    with (
        patch("infrahub.core.file_processor.registry") as mock_registry,
        patch("infrahub.core.file_processor.config") as mock_config,
    ):
        mock_registry.storage = mock_storage
        mock_config.SETTINGS.storage.max_file_size = 50

        processor = FileUploadProcessor(file=upload_file)
        result = await processor.process()

        assert result.file_name == result.storage_id
