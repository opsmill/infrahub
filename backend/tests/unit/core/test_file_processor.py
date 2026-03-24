import hashlib
from collections.abc import Generator
from dataclasses import dataclass
from io import BytesIO

import pytest
from starlette.datastructures import UploadFile

from infrahub import config
from infrahub.core import registry
from infrahub.core.file_processor import FileUploadProcessor
from infrahub.exceptions import ValidationError
from tests.adapters.storage import DummyObjectStorage


def create_upload_file(content: bytes, filename: str | None = "test.bin") -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename)


@dataclass
class UploadedFileData:
    content: bytes
    filename: str
    file: UploadFile


@pytest.fixture
def upload_file() -> UploadedFileData:
    content = b"%PDF-1.4 test content"
    filename = "test.pdf"
    return UploadedFileData(
        content=content, filename=filename, file=create_upload_file(content=content, filename=filename)
    )


@pytest.fixture
def dummy_storage() -> Generator[DummyObjectStorage, None, None]:
    storage = DummyObjectStorage()
    original_storage = registry._storage
    registry._storage = storage
    yield storage
    registry._storage = original_storage


@pytest.fixture
def max_file_size_50mb() -> Generator[None, None, None]:
    original_value = config.SETTINGS.storage.max_file_size
    config.SETTINGS.storage.max_file_size = 50
    yield
    config.SETTINGS.storage.max_file_size = original_value


@pytest.fixture
def max_file_size_1mb() -> Generator[None, None, None]:
    original_value = config.SETTINGS.storage.max_file_size
    config.SETTINGS.storage.max_file_size = 1
    yield
    config.SETTINGS.storage.max_file_size = original_value


async def test_processor_returns_file_result(
    upload_file: UploadedFileData, dummy_storage: DummyObjectStorage, max_file_size_50mb: None
) -> None:
    """Test that FileUploadProcessor.process returns correct FileUploadResult."""
    processor = FileUploadProcessor(file=upload_file.file)
    result = await processor.process()

    assert result
    assert result.metadata.file_name == upload_file.filename
    assert result.metadata.file_size == len(upload_file.content)
    assert result.metadata.checksum == hashlib.sha1(upload_file.content, usedforsecurity=False).hexdigest()
    assert result.storage_id
    assert result.storage_id in dummy_storage._files


async def test_processor_calculates_sha1_checksum(
    upload_file: UploadedFileData, dummy_storage: DummyObjectStorage, max_file_size_50mb: None
) -> None:
    """Test that SHA-1 checksum is calculated correctly."""
    processor = FileUploadProcessor(file=upload_file.file)
    result = await processor.process()

    assert result
    assert result.metadata.checksum == hashlib.sha1(upload_file.content, usedforsecurity=False).hexdigest()


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param(b"hello world\n", True, id="plain-text"),
        pytest.param(b"key: value\n", True, id="yaml-text"),
        pytest.param(b"name,age\nAlice,30\n", True, id="csv-text"),
        pytest.param(b"\x00\x01\x02\x03", False, id="null-bytes"),
        pytest.param(b"\x89PNG\r\n\x1a\n\x00", False, id="png-header"),
        pytest.param(b"", True, id="empty"),
    ],
)
def test_looks_like_text(content: bytes, expected: bool) -> None:
    assert FileUploadProcessor._looks_like_text(content) is expected


async def test_processor_detects_mime_type(dummy_storage: DummyObjectStorage, max_file_size_50mb: None) -> None:
    """Test that MIME type is detected using magic bytes."""
    png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    upload_file = create_upload_file(content=png_content, filename="image.png")

    processor = FileUploadProcessor(file=upload_file)
    result = await processor.process()

    assert result
    assert result.metadata.file_type == "image/png"


@pytest.mark.parametrize(
    ("content", "filename", "expected_mime"),
    [
        pytest.param(b"key: value\nlist:\n  - item\n", "config.yaml", "application/x-yaml", id="yaml"),
        pytest.param(b"key: value\n", "config.yml", "application/x-yaml", id="yml"),
        pytest.param(b"name,age\nAlice,30\n", "data.csv", "text/csv", id="csv"),
        pytest.param(b'[section]\nkey = "val"\n', "config.toml", "application/toml", id="toml"),
        pytest.param(b"hello world\n", "readme.txt", "text/plain", id="txt"),
    ],
)
async def test_processor_detects_text_based_mime_types(
    content: bytes, filename: str, expected_mime: str, dummy_storage: DummyObjectStorage, max_file_size_50mb: None
) -> None:
    """Test that text-based file types are detected using filename extension."""
    upload_file = create_upload_file(content=content, filename=filename)

    processor = FileUploadProcessor(file=upload_file)
    result = await processor.process()

    assert result
    assert result.metadata.file_type == expected_mime


async def test_processor_fallback_mime_type(dummy_storage: DummyObjectStorage, max_file_size_50mb: None) -> None:
    """Test that unknown content falls back to application/octet-stream."""
    upload_file = create_upload_file(content=b"\x00\x01\x02\x03", filename="unknown.bin")

    processor = FileUploadProcessor(file=upload_file)
    result = await processor.process()

    assert result
    assert result.metadata.file_type == "application/octet-stream"


async def test_processor_exceeds_max_size(dummy_storage: DummyObjectStorage, max_file_size_1mb: None) -> None:
    """Test that files exceeding max_file_size raise ValidationError with human-readable size."""
    large_content = b"x" * (2**21)
    upload_file = create_upload_file(content=large_content, filename="large_file.bin")

    processor = FileUploadProcessor(file=upload_file)
    with pytest.raises(ValidationError, match=r"File size \(2\.0 MB\) exceeds maximum allowed size \(1 MB\)"):
        await processor.process()

    assert len(dummy_storage._files) == 0


async def test_processor_stores_file(
    upload_file: UploadedFileData, dummy_storage: DummyObjectStorage, max_file_size_50mb: None
) -> None:
    """Test that file is stored in storage backend with correct identifier."""
    processor = FileUploadProcessor(file=upload_file.file)
    result = await processor.process()

    assert result
    assert result.storage_id in dummy_storage._files
    assert dummy_storage._files[result.storage_id] == upload_file.content


async def test_processor_unnamed_file(dummy_storage: DummyObjectStorage, max_file_size_50mb: None) -> None:
    """Test that files without filename use storage_id as file_name."""
    upload_file = create_upload_file(content=b"content", filename=None)

    processor = FileUploadProcessor(file=upload_file)
    result = await processor.process()

    assert result
    assert result.metadata.file_name == result.storage_id
