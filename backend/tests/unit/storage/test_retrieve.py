from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from botocore.exceptions import ClientError
from fastapi_storages.base import BaseStorage

from infrahub import config
from infrahub.exceptions import NodeNotFoundError
from infrahub.storage import InfrahubObjectStorage

if TYPE_CHECKING:
    from pathlib import Path
    from typing import BinaryIO


class FailingStorage(BaseStorage):
    """Storage driver that raises the supplied error when opening an object."""

    def __init__(self, error: ClientError) -> None:
        self.error = error

    def open(self, name: str) -> BinaryIO:
        raise self.error


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

    with pytest.raises(NodeNotFoundError, match=r"nonexistent-file / StorageObject") as exc_info:
        storage.retrieve(identifier="nonexistent-file")

    assert exc_info.value.HTTP_CODE == 404
    assert isinstance(exc_info.value.__cause__, FileNotFoundError)


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

    with pytest.raises(NodeNotFoundError, match=r"nonexistent-file / StorageObject") as exc_info:
        storage.retrieve_binary(identifier="nonexistent-file")

    assert exc_info.value.HTTP_CODE == 404
    assert isinstance(exc_info.value.__cause__, FileNotFoundError)


@pytest.mark.parametrize("method_name", ["retrieve", "retrieve_binary"])
@pytest.mark.parametrize(
    ("error_code", "operation_name"),
    [("NoSuchKey", "GetObject"), ("404", "HeadObject"), ("NotFound", "HeadObject")],
)
async def test_retrieve_missing_s3_object_raises_not_found(
    local_storage_dir: Path, method_name: str, error_code: str, operation_name: str
) -> None:
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)
    error = ClientError(
        error_response={
            "Error": {"Code": error_code, "Message": "Object not found"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        },
        operation_name=operation_name,
    )
    storage._storage = FailingStorage(error=error)

    with pytest.raises(NodeNotFoundError, match=r"missing-object / StorageObject") as exc_info:
        getattr(storage, method_name)(identifier="missing-object")

    assert exc_info.value.HTTP_CODE == 404
    assert exc_info.value.identifier == "missing-object"
    assert exc_info.value.node_type == "StorageObject"
    assert exc_info.value.__cause__ is error


@pytest.mark.parametrize("method_name", ["retrieve", "retrieve_binary"])
@pytest.mark.parametrize(
    ("error_code", "status_code"),
    [("AccessDenied", 403), ("InternalError", 500), ("NoSuchBucket", 404)],
)
async def test_retrieve_s3_backend_errors_propagate(
    local_storage_dir: Path, method_name: str, error_code: str, status_code: int
) -> None:
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)
    error = ClientError(
        error_response={
            "Error": {"Code": error_code, "Message": "Storage backend failure"},
            "ResponseMetadata": {"HTTPStatusCode": status_code},
        },
        operation_name="HeadObject",
    )
    storage._storage = FailingStorage(error=error)

    with pytest.raises(ClientError, match=error_code) as exc_info:
        getattr(storage, method_name)(identifier="stored-object")

    assert exc_info.value is error


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
