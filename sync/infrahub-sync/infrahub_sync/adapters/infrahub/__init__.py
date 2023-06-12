"""DiffSync Adapter for Infrahub to manage regions."""
import inspect
import functools
import copy

from diffsync import DiffSync, DiffSyncModel


from infrahub_sync import DiffSyncMixin, SyncAdapter, SyncConfig
from infrahub_client import InfrahubClientSync, InfrahubNodeSync, NodeNotFound


def infrahub_node_to_diffsync(node: InfrahubNodeSync) -> dict:
    data = {"local_id": str(node.id)}
    for attr_name in node._schema.attribute_names:
        attr = getattr(node, attr_name)
        data[attr_name] = attr.value

    return data


def update_node(node, attrs):
    for attr_name, attr_value in attrs.items():
        if attr_name in node._schema.attribute_names:
            attr = getattr(node, attr_name)
            attr.value = attr_value

    return node


class InfrahubAdapter(DiffSyncMixin, DiffSync):
    type = "Infrahub"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, **kwargs):
        super().__init__(*args, **kwargs)

        self.target = target

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
            data = infrahub_node_to_diffsync(node)
            item = model(**data)
            self.add(item)


class InfrahubModel(DiffSyncModel):
    @classmethod
    def create(cls, diffsync, ids: dict, attrs: dict):
        cls.__name__
        data = copy.deepcopy(ids)
        data.update(attrs)

        # schema = diffsync.client.schema.get(name=cls.__name__)
        node = diffsync.client.create(kind=cls.__name__, data=data)
        node.save()
        return super().create(diffsync, ids=ids, attrs=attrs)

    def update(self, attrs):
        # schema = self.diffsync.client.schema.get(kind=self.__class__.__name__)
        node = self.diffsync.client.get(id=self.local_id, kind=self.__class__.__name__)

        node = update_node(node=node, attrs=attrs)
        node.save()

        return super().update(attrs)
