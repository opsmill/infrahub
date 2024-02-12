import importlib
import os
from pathlib import Path
from typing import List, Optional

import yaml
from diffsync.store.local import LocalStore
from diffsync.store.redis import RedisStore

from infrahub_sync import SyncAdapter, SyncConfig, SyncInstance
from potenda import Potenda


def import_adapter(sync_instance: SyncInstance, adapter: SyncAdapter):
    directory = sync_instance.directory
    here = os.path.abspath(os.path.dirname(__file__))
    relative_directory = directory.replace(here, "")[1:]
    module = importlib.import_module(f"infrahub_sync.{relative_directory.replace('/', '.')}.{adapter.name}.adapter")
    return getattr(module, f"{adapter.name.title()}Sync")

def get_all_sync(base_directory: Optional[str] = None) -> List[SyncInstance]:
    results = []
    search_directory = Path(base_directory) if base_directory else Path(__file__).parent / "sync"
    config_files = search_directory.glob("**/config.yml")

    for config_file in config_files:
        with config_file.open("r") as file:
            directory_name = str(config_file.parent)
            config_data = yaml.safe_load(file)
            SyncConfig(**config_data)
            results.append(SyncInstance(**config_data, directory=directory_name))

    return results


def get_instance(name: Optional[str] = None, config_file: Optional[Path] = None, base_directory: Optional[str] = None) -> Optional[SyncInstance]:
    if config_file:
        config_file_path = Path(config_file).resolve()
    else:
        config_file_path = None

    if base_directory:
        base_directory_path = Path(base_directory).resolve()
    elif config_file_path:
        base_directory_path = config_file_path.parent
    else:
        base_directory_path = Path.cwd()

    if config_file_path:
        if config_file_path.is_absolute() or base_directory_path is None:
            configuration = config_file_path
        else:
            configuration = base_directory_path / config_file_path
        directory = base_directory_path if base_directory_path else configuration.parent
        if configuration.is_file():
            with configuration.open("r") as file:
                config_data = yaml.safe_load(file)
                return SyncInstance(**config_data, directory=str(directory))
    else:
        all_sync_instances = get_all_sync(base_directory=base_directory)
        for item in all_sync_instances:
            if item.name == name:
                return item


def get_potenda_from_instance(
    sync_instance: SyncInstance, branch: Optional[str] = None, show_progress: Optional[bool] = True
) -> Potenda:
    source = import_adapter(sync_instance=sync_instance, adapter=sync_instance.source)
    destination = import_adapter(sync_instance=sync_instance, adapter=sync_instance.destination)

    internal_storage_engine = LocalStore()

    if sync_instance.store:
        if sync_instance.store.type == "redis":
            if sync_instance.store.settings and isinstance(sync_instance.store.settings, dict):
                redis_settings = sync_instance.store.settings
                internal_storage_engine = RedisStore(**redis_settings)
            else:
                internal_storage_engine = RedisStore()

    if sync_instance.source.name == "infrahub" and branch:
        src = source(
            config=sync_instance,
            target="source",
            adapter=sync_instance.source,
            branch=branch,
            internal_storage_engine=internal_storage_engine
            )
    else:
        src = source(
            config=sync_instance,
            target="source",
            adapter=sync_instance.source,
            internal_storage_engine=internal_storage_engine
            )
    if sync_instance.destination.name == "infrahub" and branch:
        dst = destination(
            config=sync_instance,
            target="destination",
            adapter=sync_instance.destination,
            branch=branch,
            internal_storage_engine=internal_storage_engine
            )
    else:
        dst = destination(
            config=sync_instance,
            target="destination",
            adapter=sync_instance.destination,
            internal_storage_engine=internal_storage_engine
            )

    ptd = Potenda(
        destination=dst,
        source=src,
        config=sync_instance,
        top_level=sync_instance.order,
        show_progress=show_progress,
    )

    return ptd
