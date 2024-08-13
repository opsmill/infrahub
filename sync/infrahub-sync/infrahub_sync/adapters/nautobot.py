from __future__ import annotations

# pylint: disable=R0801
import os
from typing import TYPE_CHECKING, Any, Mapping

import pynautobot

from diffsync import Adapter, DiffSyncModel
from infrahub_sync import (
    DiffSyncMixin,
    DiffSyncModelMixin,
    SchemaMappingModel,
    SyncAdapter,
    SyncConfig,
)

from .utils import get_value

if TYPE_CHECKING:
    from pynautobot.core.response import Record as NautobotRecord


class NautobotAdapter(DiffSyncMixin, Adapter):
    type = "Nautobot"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, **kwargs):
        super().__init__(*args, **kwargs)

        self.target = target
        self.client = self._create_nautobot_client(adapter)
        self.config = config

    def _create_nautobot_client(self, adapter: SyncAdapter):
        settings = adapter.settings or {}
        url = os.environ.get("NAUTOBOT_ADDRESS") or os.environ.get("NAUTOBOT_URL") or settings.get("url")
        token = os.environ.get("NAUTOBOT_TOKEN") or settings.get("token")

        if not url or not token:
            raise ValueError("Both url and token must be specified!")

        return pynautobot.api(url, token=token, threading=True, max_workers=5, retries=3)

    def model_loader(self, model_name, model):
        # for element in self.config.schema_mapping:
        #     if not element.name == model_name:
        #         continue

        #     app_name, resource_name = element.mapping.split(".")

        #     if isinstance(objs, dict):
        #         objs = model.filter_records(list(objs.values()))
        #     elif isinstance(objs, list):
        #         objs = model.filter_records(objs)
        #     print(f"{self.type}: Loading {len(objs)}/{total} {resource_name}")

        #     transformed_objs = model.transform_records(objs)
        #     for obj in transformed_objs:
        #         data = self.nautobot_obj_to_diffsync(obj=obj, mapping=element, model=model)
        #         item = model(**data)
        #         self.add(item)
        for element in self.config.schema_mapping:
            if not element.name == model_name:
                continue

            app_name, resource_name = element.mapping.split(".")

            nautobot_app = getattr(self.client, app_name)
            nautobot_model = getattr(nautobot_app, resource_name)

            count = nautobot_model.count()
            objs = nautobot_model.filter([])  # Retrieve all objects
            if count != len(objs):
                raise ValueError(
                    f"Nautobot didn't return the expected number of objects. Got {len(objs)} instead of {count}"
                )
            total = len(objs)

            dict_objs = []
            # Convert to dict for filtering and transformation
            for obj in objs:
                data = self.nautobot_obj_to_diffsync(obj=obj, mapping=element, model=model)
                dict_objs.append(data)

            # Apply filtering and transformation
            filtered_objs = model.filter_records(dict_objs)
            print(f"{self.type}: Loading {len(filtered_objs)}/{total} {resource_name}")
            transformed_objs = model.transform_records(filtered_objs)

            # Instantiate models after filtering and transformation
            for obj in transformed_objs:
                item = model(**obj)
                self.add(item)

    def nautobot_obj_to_diffsync(self, obj: NautobotRecord, mapping: SchemaMappingModel, model: NautobotModel) -> dict:  # pylint: disable=too-many-branches
        data: dict[str, Any] = {"local_id": str(obj.id)}

        for field in mapping.fields:  # pylint: disable=too-many-nested-blocks
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
                nodes = [item for item in all_nodes_for_reference]  # noqa: C416
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


class NautobotModel(DiffSyncModelMixin, DiffSyncModel):
    @classmethod
    def create(
        cls,
        ids: Mapping[Any, Any],
        attrs: Mapping[Any, Any],
        adapter: Adapter,
    ):
        # TODO
        return super().create(adapter, ids=ids, attrs=attrs)

    def update(self, attrs):
        # TODO
        return super().update(attrs)

    @classmethod
    def filter_records(cls, records: list[Any]) -> list[Any]:
        """
        Placeholder method for filtering records.

        This method can be overridden in specific models generated by the template to apply
        specific filtering logic based on filters defined in the configuration.
        """
        return records

    @classmethod
    def transform_records(cls, records: list[Any]) -> list[Any]:
        """
        Placeholder method for transforming records.

        This method can be overridden in specific models generated by the template to apply
        specific transforming logic based on transformations defined in the configuration.
        """
        return records
