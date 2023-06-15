import pynetbox
from diffsync import DiffSync, DiffSyncModel
from infrahub_sync import (
    DiffSyncMixin,
    DiffSyncModelMixin,
    SchemaMappingModel,
    SyncAdapter,
    SyncConfig,
)
from pynetbox.core.response import Record as NetboxRecord


def get_value(obj, name: str):
    if "." not in name:
        return getattr(obj, name)

    first_name, remaining_part = name.split(".", maxsplit=1)
    return get_value(obj=getattr(obj, first_name), name=remaining_part)


class NetboxAdapter(DiffSyncMixin, DiffSync):
    type = "Netbox"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, **kwargs):
        super().__init__(*args, **kwargs)

        self.target = target

        if not isinstance(adapter.settings, dict) or "url" not in adapter.settings or "token" not in adapter.settings:
            raise ValueError("Both url and token must be specified!")

        self.client = pynetbox.api(adapter.settings["url"], token=adapter.settings["token"])
        self.config = config

    def model_loader(self, model_name, model):
        for element in self.config.schema_mapping:
            if not element.name == model_name:
                continue

            app_name, model_name = element.mapping.split(".")

            netbox_app = getattr(self.client, app_name)
            netbox_model = getattr(netbox_app, model_name)

            objs = netbox_model.all()

            for obj in objs:
                data = self.netbox_obj_to_diffsync(obj=obj, mapping=element, model=model)
                item = model(**data)
                self.add(item)

    def netbox_obj_to_diffsync(self, obj: NetboxRecord, mapping: SchemaMappingModel, model: DiffSyncModel) -> dict:
        data = {"local_id": str(obj.id)}

        for field in mapping.fields:
            field_is_list = model.is_list(name=field.name)

            if field.static:
                data[field.name] = field.static
            elif not field_is_list and field.mapping and not field.reference:
                data[field.name] = get_value(obj, field.mapping)
            elif field_is_list and field.mapping and not field.reference:
                raise NotImplementedError(
                    "it's not supported yet to have ann attribute of type list with a simle reference"
                )

            elif field.mapping and field.reference:
                nodes = [item for item in self.store.get_all(model=field.reference)]
                # breakpoint()
                if not field_is_list:
                    node = get_value(obj, field.mapping)
                    matching_nodes = [item for item in nodes if item.local_id == str(node.id)]
                    if len(matching_nodes) == 0:
                        raise IndexError(f"Unable to locate the node {model} {node.id}")
                    node = matching_nodes[0]
                    data[field.name] = node.get_unique_id()

                else:
                    data[field.name] = []
                    for node in get_value(obj, field.mapping):
                        matching_nodes = [item for item in nodes if item.local_id == str(node.id)]
                        if len(matching_nodes) == 0:
                            raise IndexError(f"Unable to locate the node {field.reference} {node.id}")
                        data[field.name].append(matching_nodes[0].get_unique_id())

        return data


class NetboxModel(DiffSyncModelMixin, DiffSyncModel):
    pass
