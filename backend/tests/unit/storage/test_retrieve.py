from __future__ import annotations

import io
from typing import TYPE_CHECKING

import botocore.exceptions
import pytest
from fastapi_storages.base import BaseStorage

from infrahub import config
from infrahub.exceptions import NodeNotFoundError
from infrahub.storage import InfrahubObjectStorage

if TYPE_CHECKING:
    from pathlib import Path
    from typing import BinaryIO


class FailingDriver(BaseStorage):
    """Storage driver whose reads fail with the given error."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def open(self, name: str) -> BinaryIO:
        raise self.error


def s3_error(code: str) -> botocore.exceptions.ClientError:
    return botocore.exceptions.ClientError(
        error_response={"Error": {"Code": code, "Message": code}}, operation_name="HeadObject"
    )


@pytest.mark.parametrize("code", ["NoSuchKey", "NotFound", "404"])
async def test_retrieve_binary_reports_a_missing_s3_key_as_not_found(local_storage_dir: Path, code: str) -> None:
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)
    storage._storage = FailingDriver(error=s3_error(code=code))

    with pytest.raises(
        NodeNotFoundError, match=r"Unable to find the node missing-object / StorageObject in the database\."
    ):
        storage.retrieve_binary(identifier="missing-object")


async def test_retrieve_binary_lets_other_s3_errors_through(local_storage_dir: Path) -> None:
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)
    error = s3_error(code="AccessDenied")
    storage._storage = FailingDriver(error=error)

    with pytest.raises(
        botocore.exceptions.ClientError,
        match=r"^An error occurred \(AccessDenied\) when calling the HeadObject operation: AccessDenied$",
    ) as exc_info:
        storage.retrieve_binary(identifier="stored-object")

    assert exc_info.value is error


async def test_retrieve_returns_decoded_string(local_storage_dir: Path) -> None:
    """Test that retrieve() returns decoded string."""
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)

    content = b"Hello, world!"
    identifier = "test-text-file"
    storage.store(identifier=identifier, content=io.BytesIO(content))

    result = storage.retrieve(identifier=identifier)

    assert isinstance(result, str)
    assert result == "Hello, world!"


async def test_retrieve_with_utf8_content(local_storage_dir: Path) -> None:
    """Test that retrieve() correctly handles UTF-8 encoded content."""
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)

    text = "Hello, 世界! 🌍"
    content = text.encode("utf-8")
    identifier = "test-utf8-file"
    storage.store(identifier=identifier, content=io.BytesIO(content))

    result = storage.retrieve(identifier=identifier)

    assert isinstance(result, str)
    assert result == text


async def test_retrieve_nonexistent_raises_error(local_storage_dir: Path) -> None:
    """Test that retrieve() raises NodeNotFoundError for missing files."""
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)

    with pytest.raises(NodeNotFoundError):
        storage.retrieve(identifier="nonexistent-file")


async def test_retrieve_binary_returns_raw_bytes(local_storage_dir: Path) -> None:
    """Test that retrieve_binary() returns raw bytes without decoding."""
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)

    content = b"Hello, world!"
    identifier = "test-text-file"
    storage.store(identifier=identifier, content=io.BytesIO(content))

    result = storage.retrieve_binary(identifier=identifier)

    assert isinstance(result, bytes)
    assert result == content


async def test_retrieve_binary_with_binary_content(local_storage_dir: Path) -> None:
    """Test that retrieve_binary() correctly handles binary content (e.g., PNG image)."""
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)

    # PNG header
    content = b"\x89PNG\r\n\x1a\n" + b"\x00\xff\xfe\xfd" * 100
    identifier = "test-binary-file"
    storage.store(identifier=identifier, content=io.BytesIO(content))

    result = storage.retrieve_binary(identifier=identifier)

    assert isinstance(result, bytes)
    assert result == content
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


async def test_retrieve_binary_nonexistent_raises_error(local_storage_dir: Path) -> None:
    """Test that retrieve_binary() raises NodeNotFoundError for missing files."""
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)

    with pytest.raises(NodeNotFoundError):
        storage.retrieve_binary(identifier="nonexistent-file")


async def test_retrieve_vs_retrieve_binary(local_storage_dir: Path) -> None:
    """Test the difference between retrieve() and retrieve_binary()."""
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)

    content = b"Hello, world!"
    identifier = "test-comparison"
    storage.store(identifier=identifier, content=io.BytesIO(content))

    text_result = storage.retrieve(identifier=identifier)
    assert isinstance(text_result, str)
    assert text_result == "Hello, world!"

    binary_result = storage.retrieve_binary(identifier=identifier)
    assert isinstance(binary_result, bytes)
    assert binary_result == content

    assert text_result.encode("utf-8") == binary_result
    assert binary_result.decode("utf-8") == text_result
