from __future__ import annotations

# pylint: disable=R0801
import os
from typing import TYPE_CHECKING, Any, Dict

try:
    from ipfabric import IPFClient
except Exception as e:
    print(e)

from diffsync import DiffSyncModel
from infrahub_sync import (
    DiffSyncMixin,
    DiffSyncModelMixin,
    SchemaMappingModel,
    SyncAdapter,
    SyncConfig,
)

ipf_filters = {"tables/inventory/summary/platforms": {
    "and": [
      {
        "platform": [
          "empty",
          False
        ]
      }
    ]
  },
  "tables/inventory/summary/models": {
    "and": [
      {
        "model": [
          "empty",
          False
        ]
      }
    ]
  }, 
  "tables/inventory/pn": {
    "and": [
      {
        "name": [
          "empty",
          False
        ]
      }
    ]
  }}

try:
    from diffsync import Adapter as DiffSync  # type: ignore[attr-defined]
except ImportError:
    from diffsync import DiffSync  # type: ignore[no-redef]

class IpfabricsyncAdapter(DiffSyncMixin, DiffSync):
    type = "IPFabric"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, **kwargs):
        super().__init__(*args, **kwargs)

        self.target = target
        self.client = self._create_ipfabric_client(adapter)
        self.config = config

    def _create_ipfabric_client(self, adapter: SyncAdapter):

        settings = adapter.settings or {}
        return IPFClient(**settings)

    def build_mapping(self, reference, obj):
        # Get object class and model name from the store
        object_class, modelname = self.store._get_object_class_and_model(model=reference)

        # Find the schema element matching the model name
        schema_element = next(
            (element for element in self.config.schema_mapping if element.name == modelname),
            None
        )

        # Collect all relevant field mappings for identifiers
        new_identifiers = []

        # Convert schema_element.fields to a dictionary for fast lookup
        field_dict = {field.name: field.mapping for field in schema_element.fields}

        # Loop through object_class._identifiers to find corresponding field mappings
        for identifier in object_class._identifiers:
            if identifier in field_dict:
                new_identifiers.append(field_dict[identifier])

        # Construct the unique identifier, using a fallback if a key isn't found
        unique_id = "__".join(str(obj.get(key, '')) for key in new_identifiers)
        return unique_id

    def model_loader(self, model_name, model):
        for element in self.config.schema_mapping:
            if not element.name == model_name:
                continue

            table = self.client.fetch_all(element.mapping, filters=ipf_filters.get(element.mapping))
            print(f"{self.type}: Loading {len(table)} from `{element.mapping}`")

            for obj in table:
                data = self.ipfabric_dict_to_diffsync(obj=obj, mapping=element, model=model)
                item = model(**data)
                self.update_or_add_model_instance(item)

    def ipfabric_dict_to_diffsync(self, obj: dict, mapping: SchemaMappingModel, model: IpfabricsyncModel) -> dict:  # pylint: disable=too-many-branches
        data: Dict[str, Any] = {"local_id": str(obj['id'])}

        for field in mapping.fields:  # pylint: disable=too-many-nested-blocks
            field_is_list = model.is_list(name=field.name)

            if field.static:
                data[field.name] = field.static
            elif not field_is_list and field.mapping and not field.reference:
                value = obj.get(field.mapping)
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
                    if node := obj[field.mapping]:
                        matching_nodes = []
                        node_id = self.build_mapping(field.reference, obj)
                        matching_nodes = [item for item in nodes if str(item) == node_id]
                        if len(matching_nodes) == 0:
                            raise IndexError(f"Unable to locate the node {model} {node_id}")
                        node = matching_nodes[0]
                        data[field.name] = node.get_unique_id()

        return data


class IpfabricsyncModel(DiffSyncModelMixin, DiffSyncModel):
    pass
