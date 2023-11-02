import os
from pathlib import Path

import pytest

from infrahub.exceptions import NodeNotFound
from infrahub.storage.local import InfrahubLocalStorage, LocalStorageSettings
from infrahub_sdk import UUIDT


class set_directory(object):
    """Sets the cwd within the context

    Args:
        path (Path): The path to the cwd
    """

    def __init__(self, path: Path):
        self.path = path
        self.origin = Path().absolute()

    def __enter__(self):
        os.chdir(self.path)

    def __exit__(self, *args, **kwargs):
        os.chdir(self.origin)


async def test_init(helper, local_storage_dir: str, file1_in_storage: str):
    storage = await InfrahubLocalStorage.init(settings={"directory": local_storage_dir})
    assert isinstance(storage.settings, LocalStorageSettings)

    with set_directory(Path(os.path.dirname(local_storage_dir))):
        storage = await InfrahubLocalStorage.init()
        assert isinstance(storage.settings, LocalStorageSettings)
        assert storage.directory_root == local_storage_dir


async def test_generate_path(helper, local_storage_dir: str, file1_in_storage: str):
    storage = await InfrahubLocalStorage.init(settings={"directory": local_storage_dir})

    assert storage.generate_path(identifier="test1") == f"{local_storage_dir}/test1"


async def test_retrieve_file(helper, local_storage_dir: str, file1_in_storage: str):
    storage = await InfrahubLocalStorage.init(settings={"directory": local_storage_dir})

    file1 = await storage.retrieve(identifier=file1_in_storage)
    assert file1


async def test_retrieve_file_does_not_exist(helper, local_storage_dir: str):
    storage = await InfrahubLocalStorage.init(settings={"directory": local_storage_dir})
    with pytest.raises(NodeNotFound):
        await storage.retrieve(identifier="doesnotexist")


async def test_store_file(
    helper,
    local_storage_dir: str,
):
    storage = await InfrahubLocalStorage.init(settings={"directory": local_storage_dir})

    fixture_dir = helper.get_fixtures_dir()
    files_dir = os.path.join(fixture_dir, "schemas")
    filenames = [item.name for item in os.scandir(files_dir) if item.is_file()]

    content_file1 = Path(os.path.join(files_dir, filenames[0])).read_bytes()
    identifier = str(UUIDT())
    await storage.store(identifier=identifier, content=content_file1)

    file1 = Path(os.path.join(local_storage_dir, identifier))
    assert file1.exists()
    assert file1.read_bytes() == content_file1
