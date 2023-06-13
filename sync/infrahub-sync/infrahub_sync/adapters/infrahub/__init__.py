"""DiffSync Adapter for Infrahub to manage regions."""
import inspect
import functools
import copy

from diffsync import DiffSync, DiffSyncModel


from infrahub_sync import DiffSyncMixin, SyncAdapter, SyncConfig
from infrahub_sync.generator import has_field
from infrahub_client import InfrahubClientSync, InfrahubNodeSync, NodeNotFound, NodeSchema, NodeStoreSync
from infrahub_client.utils import compare_lists

def update_node(node: NodeSchema, attrs: dict):
    for attr_name, attr_value in attrs.items():
        if attr_name in node._schema.attribute_names:
            attr = getattr(node, attr_name)
            attr.value = attr_value

        for rel in node._schema.relationships:
            if attr_name == rel.name and rel.cardinality == "one":
                peer = node.client.store.get(key=attr_value, kind=rel.peer)
                # data[key] = peer.id

                attr = getattr(node, attr_name)
                attr.peer_id = peer.id
            if attr_name == rel.name and rel.cardinality == "many":

                new_peer_ids = [ node.client.store.get(key=value, kind=rel.peer).id for value in list(attr_value)]
                # data[key] = new_values
                attr = getattr(node, attr_name)
                existing_peer_ids = attr.peer_ids

                in_both, existing_only, new_only = compare_lists(existing_peer_ids, new_peer_ids)

                for id in existing_only:
                    attr.remove(id)

                for id in new_only:
                    attr.add(id)

    return node


class InfrahubAdapter(DiffSyncMixin, DiffSync):
    type = "Infrahub"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, **kwargs):
        super().__init__(*args, **kwargs)

        self.target = target
        self.config = config

        if "url" not in adapter.settings:
            raise ValueError("url must be specified!")

        self.client = InfrahubClientSync(address=adapter.settings["url"])

        # We need to identify with an account until we have some auth in place
        remote_account = "Netbox"
        try:
            self.account = self.client.get(kind="Account", name__value=remote_account)
        except NodeNotFound as exc:
            self.account = self.client.create(kind="Account", name=remote_account, password="nopassword")
            self.account.save()

    def model_loader(self, model_name: str, model):
        nodes = self.client.all(kind=model.__name__, populate_store=True)
        for node in nodes:
            data = self.infrahub_node_to_diffsync(node)
            item = model(**data)
            self.client.store.set(key=item.get_unique_id(), node=node)
            self.add(item)

    def infrahub_node_to_diffsync(self, node: InfrahubNodeSync) -> dict:
        """Convert an InfrahubNode into a dict that will be used to create a DiffSyncModel."""
        data = {"local_id": str(node.id)}

        for attr_name in node._schema.attribute_names:
            if has_field(config=self.config, name=node._schema.name, field=attr_name):
                attr = getattr(node, attr_name)
                data[attr_name] = attr.value

        for rel_schema in node._schema.relationships:
            if not has_field(config=self.config, name=node._schema.name, field=rel_schema.name):
                continue
            if rel_schema.cardinality == "one":

                rel = getattr(node, rel_schema.name)
                peer = self.client.store.get(key=rel.id, kind=rel_schema.peer)

                peer_data = self.infrahub_node_to_diffsync(peer)
                peer_model = getattr(self, rel_schema.peer.lower())
                peer_item = peer_model(**peer_data)

                data[rel_schema.name] = peer_item.get_unique_id()

        return data


def diffsync_to_infrahub(ids: dict, attrs: dict, store: NodeStoreSync, schema: NodeSchema):

        data = copy.deepcopy(ids)
        data.update(attrs)

        for key in list(data.keys()):
            for rel in schema.relationships:
                if key == rel.name and rel.cardinality == "one":
                    peer = store.get(key=data[key], kind=rel.peer)
                    data[key] = peer.id
                if key == rel.name and rel.cardinality == "many":
                    new_values = [ store.get(key=value, kind=rel.peer).id for value in list(data[key])]
                    data[key] = new_values

        return data

class InfrahubModel(DiffSyncModel):
    @classmethod
    def create(cls, diffsync, ids: dict, attrs: dict):

        schema = diffsync.client.schema.get(kind=cls.__name__)

        data = diffsync_to_infrahub(ids=ids, attrs=attrs, schema=schema, store=diffsync.client.store)

        source = diffsync.account
        create_data = diffsync.client.schema.generate_payload_create(
            schema=schema, data=data, source=source.id, is_protected=True
        )

        node = diffsync.client.create(kind=cls.__name__, data=create_data)
        node.save()
        return super().create(diffsync, ids=ids, attrs=attrs)

    def update(self, attrs):
        # schema = self.diffsync.client.schema.get(kind=self.__class__.__name__)
        node = self.diffsync.client.get(id=self.local_id, kind=self.__class__.__name__)

        # schema = self.diffsync.client.schema.get(kind=self.__class__.__name__)

        # diffsync_to_infrahub(ids={}, attrs=attrs, schema=schema, store=self.diffsync.client.store)
        node = update_node(node=node, attrs=attrs)
        node.save()

        return super().update(attrs)
