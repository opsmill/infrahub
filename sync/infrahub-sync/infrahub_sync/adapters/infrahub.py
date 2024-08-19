import copy
import os
from typing import Any, Mapping

from infrahub_sdk import (
    Config,
    InfrahubClientSync,
    InfrahubNodeSync,
    NodeSchema,
    NodeStoreSync,
)
from infrahub_sdk.exceptions import NodeNotFoundError
from infrahub_sdk.utils import compare_lists

from diffsync import Adapter, DiffSyncModel
from infrahub_sync import (
    DiffSyncMixin,
    DiffSyncModelMixin,
    SyncAdapter,
    SyncConfig,
)
from infrahub_sync.generator import has_field


def update_node(node: InfrahubNodeSync, attrs: dict):
    for attr_name, attr_value in attrs.items():
        if attr_name in node._schema.attribute_names:
            attr = getattr(node, attr_name)
            attr.value = attr_value

        if attr_name in node._schema.relationship_names:
            for rel_schema in node._schema.relationships:
                if attr_name == rel_schema.name and rel_schema.cardinality == "one":
                    if attr_value:
                        if rel_schema.kind != "Generic":
                            peer = node._client.store.get(
                                key=attr_value, kind=rel_schema.peer, raise_when_missing=False
                            )
                        else:
                            peer = node._client.store.get(key=attr_value, raise_when_missing=False)
                        if not peer:
                            print(f"Unable to find {rel_schema.peer} [{attr_value}] in the Store - Ignored")
                            continue
                        setattr(node, attr_name, peer)
                    else:
                        # TODO: Do we want to delete old relationship here ?
                        pass

                if attr_name == rel_schema.name and rel_schema.cardinality == "many":
                    attr = getattr(node, attr_name)
                    existing_peer_ids = attr.peer_ids
                    new_peer_ids = [
                        node._client.store.get(key=value, kind=rel_schema.peer).id for value in list(attr_value)
                    ]
                    _, existing_only, new_only = compare_lists(existing_peer_ids, new_peer_ids)  # noqa: F841

                    for existing_id in existing_only:
                        attr.remove(existing_id)

                    for new_id in new_only:
                        attr.add(new_id)

    return node


def diffsync_to_infrahub(ids: Mapping[Any, Any], attrs: Mapping[Any, Any], store: NodeStoreSync, schema: NodeSchema):
    data = copy.deepcopy(dict(ids))
    data.update(dict(attrs))

    for key in list(data.keys()):
        if key in schema.relationship_names:
            for rel_schema in schema.relationships:
                if key == rel_schema.name and rel_schema.cardinality == "one":
                    if data[key] is None:
                        del data[key]
                        continue
                    if rel_schema.kind != "Generic":
                        peer = store.get(key=data[key], kind=rel_schema.peer, raise_when_missing=False)
                    else:
                        peer = store.get(key=data[key], raise_when_missing=False)
                    if not peer:
                        print(f"Unable to find {rel_schema.peer} [{data[key]}] in the Store - Ignored")
                        continue

                    data[key] = peer.id
                if key == rel_schema.name and rel_schema.cardinality == "many":
                    if data[key] is None:
                        del data[key]
                        continue
                    new_values = [store.get(key=value, kind=rel_schema.peer).id for value in list(data[key])]
                    data[key] = new_values

    return data


class InfrahubAdapter(DiffSyncMixin, Adapter):
    type = "Infrahub"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, branch: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = target
        self.config = config

        settings = adapter.settings or {}
        url = os.environ.get("INFRAHUB_ADDRESS") or os.environ.get("INFRAHUB_URL") or settings.get("url")
        token = os.environ.get("INFRAHUB_API_TOKEN") or settings.get("token")

        if not url or not token:
            raise ValueError("Both url and token must be specified!")

        if branch:
            sdk_config = Config(timeout=60, default_branch=branch, api_token=token)
        else:
            sdk_config = Config(timeout=60, api_token=token)

        self.client = InfrahubClientSync(address=url, config=sdk_config)

        # We need to identify with an account until we have some auth in place
        remote_account = config.source.name
        try:
            self.account = self.client.get(kind="CoreAccount", name__value=remote_account)
        except NodeNotFoundError:
            self.account = None

    def model_loader(self, model_name: str, model: "InfrahubModel"):
        """
        Load and process models using schema mapping filters and transformations.

        This method retrieves data from Infrahub, applies filters and transformations
        as specified in the schema mapping, and loads the processed data into the adapter.
        """
        element = next((el for el in self.config.schema_mapping if el.name == model_name), None)
        if element:
            # Retrieve all nodes corresponding to model_name (list of InfrahubNodeSync)
            nodes = self.client.all(kind=model_name, populate_store=True)

            # Transform the list of InfrahubNodeSync into a list of (node, dict) tuples
            node_dict_pairs = [(node, self.infrahub_node_to_diffsync(node=node)) for node in nodes]
            total = len(node_dict_pairs)

            # Extract the list of dicts for filtering and transforming
            list_obj = [pair[1] for pair in node_dict_pairs]

            if self.config.source.name.title() == self.type.title():
                # Filter records
                filtered_objs = model.filter_records(records=list_obj, schema_mapping=element)
                print(f"{self.type}: Loading {len(filtered_objs)}/{total} {model_name}")
                # Transform records
                transformed_objs = model.transform_records(records=filtered_objs, schema_mapping=element)
            else:
                print(f"{self.type}: Loading all {total} {model_name}")
                transformed_objs = list_obj

            # Create model instances after filtering and transforming
            for transformed_obj in transformed_objs:
                original_node = next(node for node, obj in node_dict_pairs if obj == transformed_obj)
                item = model(**transformed_obj)
                unique_id = item.get_unique_id()
                self.client.store.set(key=unique_id, node=original_node)
                self.update_or_add_model_instance(item)

    def infrahub_node_to_diffsync(self, node: InfrahubNodeSync) -> dict:
        """Convert an InfrahubNode into a dict that will be used to create a DiffSyncModel."""
        data: dict[str, Any] = {"local_id": str(node.id)}

        for attr_name in node._schema.attribute_names:
            if has_field(config=self.config, name=node._schema.kind, field=attr_name):
                attr = getattr(node, attr_name)
                # Is it the right place to do it or are we missing some de-serialize ?
                # got a ValidationError from pydantic while trying to get the model(**data)
                # for IPHost and IPInterface
                if attr.value and not isinstance(attr.value, str):
                    data[attr_name] = str(attr.value)
                else:
                    data[attr_name] = attr.value

        for rel_schema in node._schema.relationships:
            if not has_field(config=self.config, name=node._schema.kind, field=rel_schema.name):
                continue
            if rel_schema.cardinality == "one":
                rel = getattr(node, rel_schema.name)
                if not rel.id:
                    continue
                if rel_schema.kind != "Generic":
                    peer_node = self.client.store.get(key=rel.id, kind=rel_schema.peer, raise_when_missing=False)
                else:
                    peer_node = self.client.store.get(key=rel.id, raise_when_missing=False)
                if not peer_node:
                    # I am not sure if we should end up here "normaly"
                    print(f"Debug Unable to find {rel_schema.peer} [{rel.id}] in the Store - Pulling from Infrahub")
                    peer_node = self.client.get(id=rel.id, kind=rel_schema.peer, populate_store=True)
                    if not peer_node:
                        print(f"Unable to find {rel_schema.peer} [{rel.id}]")
                        continue

                peer_data = self.infrahub_node_to_diffsync(node=peer_node)
                peer_kind = f"{peer_node._schema.namespace}{peer_node._schema.name}"
                peer_model = getattr(self, peer_kind)
                peer_item = peer_model(**peer_data)

                data[rel_schema.name] = peer_item.get_unique_id()

            elif rel_schema.cardinality == "many":
                values = []
                rel_manager = getattr(node, rel_schema.name)
                for peer in rel_manager:
                    peer_node = self.client.store.get(key=peer.id, kind=rel_schema.peer)
                    peer_data = self.infrahub_node_to_diffsync(node=peer_node)
                    peer_model = getattr(self, rel_schema.peer)
                    peer_item = peer_model(**peer_data)

                    values.append(peer_item.get_unique_id())

                data[rel_schema.name] = values

        return data


class InfrahubModel(DiffSyncModelMixin, DiffSyncModel):
    @classmethod
    def create(
        cls,
        adapter: Adapter,
        ids: Mapping[Any, Any],
        attrs: Mapping[Any, Any],
    ):
        schema = adapter.client.schema.get(kind=cls.__name__)
        data = diffsync_to_infrahub(ids=ids, attrs=attrs, schema=schema, store=adapter.client.store)
        unique_id = cls(**ids, **attrs).get_unique_id()
        source_id = None
        if adapter.account:
            source_id = adapter.account.id
        create_data = adapter.client.schema.generate_payload_create(
            schema=schema, data=data, source=source_id, is_protected=True
        )
        node = adapter.client.create(kind=cls.__name__, data=create_data)
        node.save(allow_upsert=True)
        adapter.client.store.set(key=unique_id, node=node)

        return super().create(adapter=adapter, ids=ids, attrs=attrs)

    def update(self, attrs):
        node = self.adapter.client.get(id=self.local_id, kind=self.__class__.__name__)
        node = update_node(node=node, attrs=attrs)
        node.save(allow_upsert=True)

        return super().update(attrs)
