import os
from pathlib import Path

import fastapi_storages
import pytest
from infrahub_sdk import UUIDT

from infrahub import config
from infrahub.exceptions import NodeNotFoundError
from infrahub.storage import InfrahubObjectStorage


async def test_init_local(helper, local_storage_dir: str, file1_in_storage: str):
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)
    assert isinstance(storage._storage, fastapi_storages.FileSystemStorage)
    assert config.SETTINGS.storage.local.path_ == local_storage_dir


async def test_init_s3(helper, s3_storage_bucket: str):
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)
    assert isinstance(storage._storage, fastapi_storages.InfrahubS3ObjectStorage)
    assert config.SETTINGS.storage.s3.endpoint_url == "storage.googleapis.com"


async def test_retrieve_file(helper, local_storage_dir: str, file1_in_storage: str):
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)
    file1 = storage.retrieve(identifier=file1_in_storage)
    assert file1


async def test_retrieve_file_does_not_exist(helper, local_storage_dir: str):
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)
    with pytest.raises(NodeNotFoundError):
        storage.retrieve(identifier="doesnotexist")


async def test_store_file(
    helper,
    local_storage_dir: str,
):
    storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)

    fixture_dir = helper.get_fixtures_dir()
    files_dir = os.path.join(fixture_dir, "schemas")
    filenames = [item.name for item in os.scandir(files_dir) if item.is_file()]

    content_file1 = Path(os.path.join(files_dir, filenames[0])).read_bytes()
    identifier = str(UUIDT())
    storage.store(identifier=identifier, content=content_file1)

    file1 = Path(os.path.join(local_storage_dir, identifier))
    assert file1.exists()
    assert file1.read_bytes() == content_file1
