from __future__ import annotations

import os
from typing import Any, Optional

from diffsync import Adapter, DiffSyncModel
from infrahub_sync import (
    DiffSyncMixin,
    DiffSyncModelMixin,
    SchemaMappingModel,
    SyncAdapter,
    SyncConfig,
)

from .utils import RestApiClient, derive_identifier_key, get_value


class LibrenmsAdapter(DiffSyncMixin, Adapter):
    type = "LibreNMS"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, **kwargs):
        super().__init__(*args, **kwargs)

        self.target = target
        self.client = self._create_rest_client(adapter)
        self.config = config

    def _create_rest_client(self, adapter: SyncAdapter) -> RestApiClient:
        settings = adapter.settings or {}
        url = os.environ.get("LIBRENMS_ADDRESS") or settings.get("url")
        api_endpoint = settings.get("api_endpoint", "/api/v0")
        auth_method = settings.get("auth_method", "token")
        api_token = os.environ.get("LIBRENMS_TOKEN") or settings.get("token")
        timeout = settings.get("timeout", 30)

        if not url:
            raise ValueError("API base URL must be specified!")

        if auth_method != "token" or not api_token:
            raise ValueError("Token-based authentication requires a valid API token!")

        full_base_url = f"{url.rstrip('/')}/{api_endpoint.strip('/')}"
        return RestApiClient(base_url=full_base_url, auth_method=auth_method, api_token=api_token, timeout=timeout)

    def model_loader(self, model_name: str, model: DiffSyncModel):
        for element in self.config.schema_mapping:
            if not element.name == model_name:
                continue

            resource_endpoint = element.mapping  # Use the resource endpoint from the schema mapping
            response_key = resource_endpoint.split("/")[-1]  # Get the last part of the endpoint as the key

            try:
                response_data = self.client.get(resource_endpoint)  # Fetch data from the specified resource endpoint
                objs = response_data.get(response_key, [])  # Extract the data using the derived key
            except Exception as e:
                raise ValueError(f"Error fetching data from REST API: {str(e)}")

            print(f"{self.type}: Loading {len(objs)} {response_key}")
            for obj in objs:
                data = self.obj_to_diffsync(obj=obj, mapping=element, model=model)
                item = model(**data)
                self.add(item)

    def obj_to_diffsync(
            self,
            obj: dict[str, Any],
            mapping: SchemaMappingModel,
            model: DiffSyncModel
        ) -> dict:
        obj_id = derive_identifier_key(obj=obj)
        data: dict[str, Any] = {"local_id": str(obj_id)}

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
                        if isinstance(node, dict):
                            matching_nodes = []
                            node_id = node.get("id", None)
                            matching_nodes = [item for item in nodes if item.local_id == str(node_id)]
                            if len(matching_nodes) == 0:
                                raise IndexError(f"Unable to locate the node {model} {node_id}")
                            node = matching_nodes[0]
                            data[field.name] = node.get_unique_id()
                        else:
                            # Some link are referencing the node identifier directly without the id (i.e location in device)
                            data[field.name] = node

                else:
                    data[field.name] = []
                    for node in get_value(obj, field.mapping):
                        if not node:
                            continue
                        node_id = node.get("id", None)
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


class LibrenmsModel(DiffSyncModelMixin, DiffSyncModel):
    pass
