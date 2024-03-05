import importlib
import os
import sys
from pathlib import Path
from typing import List, MutableMapping, Optional, Tuple

import yaml
from diffsync.store.local import LocalStore
from diffsync.store.redis import RedisStore
from infrahub_sdk.schema import GenericSchema, NodeSchema

from infrahub_sync import SyncAdapter, SyncConfig, SyncInstance
from infrahub_sync.generator import render_template
from potenda import Potenda


def render_adapter(
    sync_instance: SyncInstance, schema: MutableMapping[str, NodeSchema | GenericSchema]
) -> List[Tuple[str, str]]:
    files_to_render = (
        ("diffsync_models.j2", "sync_models.py"),
        ("diffsync_adapter.j2", "sync_adapter.py"),
    )
    rendered_files = []
    for adapter in [sync_instance.source, sync_instance.destination]:
        output_dir_absolute = str(os.path.join(sync_instance.directory, adapter.name))

        output_dir_path = Path(output_dir_absolute)
        if not output_dir_path.is_dir():
            output_dir_path.mkdir(exist_ok=True)

        init_file_path = output_dir_path / "__init__.py"
        if not init_file_path.exists():
            init_file_path.touch()

        for item in files_to_render:
            render_template(
                template_file=item[0],
                output_dir=output_dir_absolute,
                output_file=item[1],
                context={"schema": schema, "adapter": adapter, "config": sync_instance},
            )
            output_file_path = Path(output_dir_absolute, item[1])
            rendered_files.append((item[0], str(output_file_path)))

    return rendered_files


def import_adapter(sync_instance: SyncInstance, adapter: SyncAdapter):
    directory = Path(sync_instance.directory)
    sys.path.insert(0, str(directory))
    adapter_file_path = directory / f"{adapter.name}" / "sync_adapter.py"

    try:
        adapter_name = f"{adapter.name.title()}Sync"
        spec = importlib.util.spec_from_file_location(f"{adapter.name}.adapter", str(adapter_file_path))
        adapter_module = importlib.util.module_from_spec(spec)
        sys.modules[f"{adapter.name}.adapter"] = adapter_module
        spec.loader.exec_module(adapter_module)

        AdapterClass = getattr(adapter_module, adapter_name, None)
        if AdapterClass is None:
            raise AttributeError(f"{adapter_name} not found in adapter.py")
    except (FileNotFoundError, AttributeError) as exc:
        raise ImportError(f"{adapter_name}: {str(exc)}") from exc
    return AdapterClass


def get_all_sync(directory: Optional[str] = None) -> List[SyncInstance]:
    results = []
    search_directory = Path(directory) if directory else Path(__file__).parent
    config_files = search_directory.glob("**/config.yml")

    for config_file in config_files:
        with config_file.open("r") as file:
            directory_name = str(config_file.parent)
            config_data = yaml.safe_load(file)
            SyncConfig(**config_data)
            results.append(SyncInstance(**config_data, directory=directory_name))

    return results


def get_instance(
    name: Optional[str] = None, config_file: Optional[str] = "config.yml", directory: Optional[str] = None
) -> Optional[SyncInstance]:
    if name:
        all_sync_instances = get_all_sync(directory=directory)
        for item in all_sync_instances:
            if item.name == name:
                return item

    config_file_path = None
    if Path(config_file).is_absolute() or directory is None:
        config_file_path = Path(config_file)
    elif directory:
        config_file_path = Path(directory) / Path(config_file)

    if config_file_path:
        directory_path = config_file_path.parent
        if config_file_path.is_file():
            with config_file_path.open("r", encoding="UTF-8") as file:
                config_data = yaml.safe_load(file)
                return SyncInstance(**config_data, directory=str(directory_path))

    return None


def get_potenda_from_instance(
    sync_instance: SyncInstance, branch: Optional[str] = None, show_progress: Optional[bool] = True
) -> Potenda:
    source = import_adapter(sync_instance=sync_instance, adapter=sync_instance.source)
    destination = import_adapter(sync_instance=sync_instance, adapter=sync_instance.destination)

    source_store = LocalStore()
    destination_store = LocalStore()

    if sync_instance.store:
        if sync_instance.store.type == "redis":
            if sync_instance.store.settings and isinstance(sync_instance.store.settings, dict):
                redis_settings = sync_instance.store.settings
                source_store = RedisStore(**redis_settings, name=sync_instance.source.name)
                destination_store = RedisStore(**redis_settings, name=sync_instance.destination.name)
            else:
                source_store = RedisStore(name=sync_instance.source.name)
                destination_store = RedisStore(name=sync_instance.destination.name)

    if sync_instance.source.name == "infrahub" and branch:
        src = source(
            config=sync_instance,
            target="source",
            adapter=sync_instance.source,
            branch=branch,
            internal_storage_engine=source_store,
        )
    else:
        src = source(
            config=sync_instance,
            target="source",
            adapter=sync_instance.source,
            internal_storage_engine=source_store,
        )
    if sync_instance.destination.name == "infrahub" and branch:
        dst = destination(
            config=sync_instance,
            target="destination",
            adapter=sync_instance.destination,
            branch=branch,
            internal_storage_engine=destination_store,
        )
    else:
        dst = destination(
            config=sync_instance,
            target="destination",
            adapter=sync_instance.destination,
            internal_storage_engine=destination_store,
        )

    ptd = Potenda(
        destination=dst,
        source=src,
        config=sync_instance,
        top_level=sync_instance.order,
        show_progress=show_progress,
    )

    return ptd
