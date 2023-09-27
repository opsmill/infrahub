from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict

import pynautobot
from diffsync import DiffSync, DiffSyncModel
from infrahub_sync import (
    DiffSyncMixin,
    DiffSyncModelMixin,
    SchemaMappingModel,
    SyncAdapter,
    SyncConfig,
)

if TYPE_CHECKING:
    from pynautobot.core.response import Record as NautobotRecord


def get_value(obj, name: str):
    """Query a value in dot notation recursively on a NautobotRecord"""
    if "." not in name:
        return getattr(obj, name)

    first_name, remaining_part = name.split(".", maxsplit=1)
    sub_obj = getattr(obj, first_name)
    if not sub_obj:
        return None
    return get_value(obj=sub_obj, name=remaining_part)


class NautobotAdapter(DiffSyncMixin, DiffSync):
    type = "Nautobot"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, **kwargs):
        super().__init__(*args, **kwargs)

        self.target = target

        settings = adapter.settings or {}

        url = os.environ.get("NAUTOBOT_ADDRESS", settings.get("url", None))
        token = os.environ.get("NAUTOBOT_TOKEN", settings.get("token", None))

        if not url or not token:
            raise ValueError("Both url and token must be specified!")

        self.client = pynautobot.api(url, token=token)
        self.config = config

    def model_loader(self, model_name, model):
        for element in self.config.schema_mapping:
            if not element.name == model_name:
                continue

            app_name, resource_name = element.mapping.split(".")

            nautobot_app = getattr(self.client, app_name)
            nautobot_model = getattr(nautobot_app, resource_name)
            objs = nautobot_model.all()

            for obj in objs:
                print(f"OBJ = {obj}")
                data = self.nautobot_obj_to_diffsync(obj=obj, mapping=element, model=model)
                item = model(**data)
                self.add(item)

    def nautobot_obj_to_diffsync(self, obj: NautobotRecord, mapping: SchemaMappingModel, model: NautobotModel) -> dict:
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
                nodes = [item for item in self.store.get_all(model=field.reference)]
                if not field_is_list:
                    if node := get_value(obj, field.mapping):
                        matching_nodes = [item for item in nodes if item.local_id == str(node.id)]
                        if len(matching_nodes) == 0:
                            raise IndexError(f"Unable to locate the node {model} {node.id}")
                        node = matching_nodes[0]
                        data[field.name] = node.get_unique_id()

                else:
                    data[field.name] = []
                    for node in get_value(obj, field.mapping):
                        if not node:
                            continue
                        matching_nodes = [item for item in nodes if item.local_id == str(node.id)]
                        if len(matching_nodes) == 0:
                            raise IndexError(f"Unable to locate the node {field.reference} {node.id}")
                        data[field.name].append(matching_nodes[0].get_unique_id())

        return data


class NautobotModel(DiffSyncModelMixin, DiffSyncModel):
    pass
