import copy
from typing import Any, Dict, Mapping

from diffsync import DiffSync, DiffSyncModel
from infrahub_sdk import (
    Config,
    InfrahubClientSync,
    InfrahubNodeSync,
    NodeNotFound,
    NodeSchema,
    NodeStoreSync,
)
from infrahub_sdk.utils import compare_lists
from infrahub_sync import DiffSyncMixin, DiffSyncModelMixin, SyncAdapter, SyncConfig
from infrahub_sync.generator import has_field


def update_node(node: InfrahubNodeSync, attrs: dict):
    for attr_name, attr_value in attrs.items():
        if attr_name in node._schema.attribute_names:
            attr = getattr(node, attr_name)
            attr.value = attr_value

        if attr_name in node._schema.relationship_names:
            for rel in node._schema.relationships:
                if attr_name == rel.name and rel.cardinality == "one":
                    peer = node._client.store.get(key=attr_value, kind=rel.peer)
                    setattr(node, attr_name, peer)

                if attr_name == rel.name and rel.cardinality == "many":
                    attr = getattr(node, attr_name)
                    existing_peer_ids = attr.peer_ids
                    new_peer_ids = [node._client.store.get(key=value, kind=rel.peer).id for value in list(attr_value)]
                    in_both, existing_only, new_only = compare_lists(existing_peer_ids, new_peer_ids)  # noqa: F841

                    for id in existing_only:
                        attr.remove(id)

                    for id in new_only:
                        attr.add(id)

    return node


class InfrahubAdapter(DiffSyncMixin, DiffSync):
    type = "Infrahub"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, branch: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = target
        self.config = config
        self.branch = branch
        sdk_config = Config(timeout=60)

        if not isinstance(adapter.settings, dict) or "url" not in adapter.settings:
            raise ValueError("url must be specified!")

        if self.branch:
            self.client = InfrahubClientSync(
                address=adapter.settings["url"], default_branch=self.branch, config=sdk_config
            )
        else:
            self.client = InfrahubClientSync(address=adapter.settings["url"], config=sdk_config)

        # We need to identify with an account until we have some auth in place
        remote_account = config.source.name
        try:
            self.account = self.client.get(kind="CoreAccount", name__value=remote_account)
        except NodeNotFound:
            self.account = self.client.create(kind="CoreAccount", name=remote_account, password="nopassword")
            self.account.save()

    def model_loader(self, model_name: str, model):
        nodes = self.client.all(kind=model.__name__, populate_store=True)
        print(f"-> Loading {len(nodes)} {model_name}")
        for node in nodes:
            data = self.infrahub_node_to_diffsync(node)
            item = model(**data)
            self.client.store.set(key=item.get_unique_id(), node=node)
            self.add(item)

    def infrahub_node_to_diffsync(self, node: InfrahubNodeSync) -> dict:
        """Convert an InfrahubNode into a dict that will be used to create a DiffSyncModel."""
        data: Dict[str, Any] = {"local_id": str(node.id)}

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
                peer = self.client.store.get(key=rel.id, kind=rel_schema.peer)

                peer_data = self.infrahub_node_to_diffsync(peer)
                peer_model = getattr(self, rel_schema.peer)
                peer_item = peer_model(**peer_data)

                data[rel_schema.name] = peer_item.get_unique_id()

            elif rel_schema.cardinality == "many":
                values = []
                rel_manager = getattr(node, rel_schema.name)
                for peer in rel_manager:
                    peer_node = self.client.store.get(key=peer.id, kind=rel_schema.peer)
                    peer_data = self.infrahub_node_to_diffsync(peer_node)
                    peer_model = getattr(self, rel_schema.peer)
                    peer_item = peer_model(**peer_data)

                    values.append(peer_item.get_unique_id())

                data[rel_schema.name] = values

        return data


def diffsync_to_infrahub(ids: Mapping[Any, Any], attrs: Mapping[Any, Any], store: NodeStoreSync, schema: NodeSchema):
    data = copy.deepcopy(dict(ids))
    data.update(dict(attrs))

    for key in list(data.keys()):
        if key in schema.relationship_names:
            for rel in schema.relationships:
                if key == rel.name and rel.cardinality == "one":
                    if data[key] is None:
                        del data[key]
                        continue
                    peer = store.get(key=data[key], kind=rel.peer)
                    data[key] = peer.id
                if key == rel.name and rel.cardinality == "many":
                    if data[key] is None:
                        del data[key]
                        continue
                    new_values = [store.get(key=value, kind=rel.peer).id for value in list(data[key])]
                    data[key] = new_values

    return data


class InfrahubModel(DiffSyncModelMixin, DiffSyncModel):
    @classmethod
    def create(cls, diffsync, ids: Mapping[Any, Any], attrs: Mapping[Any, Any]):
        schema = diffsync.client.schema.get(kind=cls.__name__)

        data = diffsync_to_infrahub(ids=ids, attrs=attrs, schema=schema, store=diffsync.client.store)
        unique_id = cls(**ids, **attrs).get_unique_id()
        source = diffsync.account
        create_data = diffsync.client.schema.generate_payload_create(
            schema=schema, data=data, source=source.id, is_protected=True
        )
        node = diffsync.client.create(kind=cls.__name__, data=create_data)
        node.save()
        diffsync.client.store.set(key=unique_id, node=node)
        return super().create(diffsync, ids=ids, attrs=attrs)

    def update(self, attrs):
        node = self.diffsync.client.get(id=self.local_id, kind=self.__class__.__name__)

        node = update_node(node=node, attrs=attrs)
        node.save()

        return super().update(attrs)
