import inspect

import pytest
from pytest_httpx import HTTPXMock

from infrahub_sdk.object_store import ObjectStore, ObjectStoreSync

# pylint: disable=redefined-outer-name,unused-argument

async_methods = [method for method in dir(ObjectStore) if not method.startswith("_")]
sync_methods = [method for method in dir(ObjectStoreSync) if not method.startswith("_")]

client_types = ["standard", "sync"]

FILE_CONTENT_01 = """
    any content
    another content
    """


@pytest.fixture
async def mock_get_object_store_01(httpx_mock: HTTPXMock) -> HTTPXMock:
    httpx_mock.add_response(
        method="GET",
        text=FILE_CONTENT_01,
        match_headers={"X-Infrahub-Tracker": "object-store-get"},
    )
    return httpx_mock


@pytest.fixture
async def mock_upload_object_store_01(httpx_mock: HTTPXMock) -> HTTPXMock:
    payload = {"identifier": "xxxxxxxxxx", "checksum": "yyyyyyyyyyyyyy"}
    httpx_mock.add_response(
        method="POST",
        json=payload,
        match_headers={"X-Infrahub-Tracker": "object-store-upload"},
    )
    return httpx_mock


async def test_method_sanity():
    """Validate that there is at least one public method and that both clients look the same."""
    assert async_methods
    assert async_methods == sync_methods


@pytest.mark.parametrize("method", async_methods)
async def test_validate_method_signature(method):
    async_method = getattr(ObjectStore, method)
    sync_method = getattr(ObjectStoreSync, method)
    async_sig = inspect.signature(async_method)
    sync_sig = inspect.signature(sync_method)
    assert async_sig.parameters == sync_sig.parameters
    assert async_sig.return_annotation == sync_sig.return_annotation


@pytest.mark.parametrize("client_type", client_types)
async def test_object_store_get(client_type, clients, mock_get_object_store_01):
    client = getattr(clients, client_type)

    if client_type == "standard":
        content = await client.object_store.get(identifier="aaaaaaaaa", tracker="object-store-get")
    else:
        content = client.object_store.get(identifier="aaaaaaaaa", tracker="object-store-get")

    assert content == FILE_CONTENT_01


@pytest.mark.parametrize("client_type", client_types)
async def test_object_store_upload(client_type, clients, mock_upload_object_store_01):
    client = getattr(clients, client_type)

    if client_type == "standard":
        response = await client.object_store.upload(content=FILE_CONTENT_01, tracker="object-store-upload")
    else:
        response = client.object_store.upload(content=FILE_CONTENT_01, tracker="object-store-upload")

    assert response == {"checksum": "yyyyyyyyyyyyyy", "identifier": "xxxxxxxxxx"}
