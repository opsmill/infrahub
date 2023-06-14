import pynetbox
from diffsync import DiffSync, DiffSyncModel
from infrahub_sync import DiffSyncMixin, SchemaMappingModel, SyncAdapter, SyncConfig


def get_value(obj, name: str):
    if "." not in name:
        return getattr(obj, name)

    first_name, remaining_part = name.split(".", maxsplit=1)
    return get_value(obj=getattr(obj, first_name), name=remaining_part)


def netbox_obj_to_diffsync(mapping: SchemaMappingModel, obj) -> dict:
    data = {"local_id": str(obj.id)}

    for field in mapping.fields:
        if field.mapping:
            data[field.name] = get_value(obj, field.mapping)
        elif field.static:
            data[field.name] = field.static

    return data


class NetboxAdapter(DiffSyncMixin, DiffSync):
    type = "Netbox"

    def __init__(self, *args, target: str, adapter: SyncAdapter, config: SyncConfig, **kwargs):
        super().__init__(*args, **kwargs)

        self.target = target

        if "url" not in adapter.settings or "token" not in adapter.settings:
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
                data = netbox_obj_to_diffsync(obj=obj, mapping=element)
                item = model(**data)
                self.add(item)


class NetboxModel(DiffSyncModel):
    pass
