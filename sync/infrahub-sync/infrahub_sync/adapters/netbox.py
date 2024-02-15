from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict

import pynetbox
from diffsync import DiffSync, DiffSyncModel
from infrahub_sync import (
    DiffSyncMixin,
    DiffSyncModelMixin,
    SchemaMappingModel,
    SyncAdapter,
    SyncConfig,
)

if TYPE_CHECKING:
    from pynetbox.core.response import Record as NetboxRecord


def get_value(obj, name: str):
    """Query a value in dot notation recursively on a NetboxRecord"""
    if "." not in name:
        return getattr(obj, name)

    first_name, remaining_part = name.split(".", maxsplit=1)
    sub_obj = getattr(obj, first_name)
    if not sub_obj:
        return None
    return get_value(obj=sub_obj, name=remaining_part)


class NetboxAdapter(DiffSyncMixin, DiffSync):
    type = "Netbox"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, **kwargs):
        super().__init__(*args, **kwargs)

        self.target = target
        self.client = self._create_netbox_client(adapter)
        self.config = config

    def _create_netbox_client(self, adapter: SyncAdapter):
        settings = adapter.settings or {}
        url = os.environ.get("NETBOX_ADDRESS") or settings.get("url")
        token = os.environ.get("NETBOX_TOKEN") or settings.get("token")

        if not url or not token:
            raise ValueError("Both url and token must be specified!")

        return pynetbox.api(url, token=token)

    def model_loader(self, model_name, model):
        for element in self.config.schema_mapping:
            if not element.name == model_name:
                continue

            app_name, resource_name = element.mapping.split(".")

            netbox_app = getattr(self.client, app_name)
            netbox_model = getattr(netbox_app, resource_name)

            objs = netbox_model.all()
            print(f"{self.type}: Loading {len(objs)} {resource_name}")
            for obj in objs:
                data = self.netbox_obj_to_diffsync(obj=obj, mapping=element, model=model)
                item = model(**data)
                self.add(item)

    def netbox_obj_to_diffsync(self, obj: NetboxRecord, mapping: SchemaMappingModel, model: NetboxModel) -> dict:
        data: Dict[str, Any] = {"local_id": str(obj.id)}

        for field in mapping.fields:
            field_is_list = model.is_list(name=field.name)

            if field.static:
                data[field.name] = field.static
            elif not field_is_list and field.mapping and not field.reference:
                value = get_value(obj, field.mapping)
                if value is not None:
                    data[field.name] = value
            elif field_is_list and field.mapping and not field.reference:
                raise NotImplementedError(
                    "it's not supported yet to have an attribute of type list with a simple mapping"
                )

            elif field.mapping and field.reference:
                all_nodes_for_reference = self.store.get_all(model=field.reference)
                nodes = [item for item in all_nodes_for_reference]
                if not nodes and all_nodes_for_reference:
                    raise IndexError(
                        f"Unable to get '{field.mapping}' with '{field.reference}' reference from store."
                        f" The available models are {self.store.get_all_model_names()}"
                    )
                if not field_is_list:
                    if node := get_value(obj, field.mapping):
                        matching_nodes = []
                        node_id = getattr(node, "id", None)
                        matching_nodes = [item for item in nodes if item.local_id == str(node_id)]
                        if len(matching_nodes) == 0:
                            raise IndexError(f"Unable to locate the node {model} {node_id}")
                        node = matching_nodes[0]
                        data[field.name] = node.get_unique_id()

                else:
                    data[field.name] = []
                    for node in get_value(obj, field.mapping):
                        if not node:
                            continue
                        node_id = getattr(node, "id", None)
                        if not node_id:
                            if isinstance(node, tuple):
                                node_id = node[1] if node[0] == "id" else None
                                if not node_id:
                                    continue
                        matching_nodes = [item for item in nodes if item.local_id == str(node_id)]
                        if len(matching_nodes) == 0:
                            raise IndexError(f"Unable to locate the node {field.reference} {node_id}")
                        data[field.name].append(matching_nodes[0].get_unique_id())

        return data


class NetboxModel(DiffSyncModelMixin, DiffSyncModel):
    pass
