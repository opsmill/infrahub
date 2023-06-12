import copy
import functools

from typing import Optional, Any, List, Dict, Any

from pydantic import BaseModel


class SchemaMappingField(BaseModel):
    name: str
    mapping: Optional[str]
    static: Optional[Any]


class SchemaMappingModel(BaseModel):
    name: str
    mapping: str
    fields: List[SchemaMappingField]


class SyncAdapter(BaseModel):
    name: str
    settings: Optional[Dict[str, Any]]

class SyncConfig(BaseModel):
    name: str
    source: SyncAdapter
    destination: SyncAdapter
    schema_mapping: List[SchemaMappingModel]


class SyncInstance(SyncConfig):
    directory: str


class DiffSyncMixin:
    def load(self):
        for item in self.top_level:
            try:
                method = getattr(self, f"load_{item}")
                method()
            except AttributeError as exc:
                pass

    def __getattr__(self, item: str):
        if not item.startswith("load_"):
            raise AttributeError

        model_name = item.replace("load_", "")

        if not hasattr(self, model_name):
            raise AttributeError(f"Unable to find the model {model_name}")

        model = getattr(self, model_name)
        return functools.partial(self.model_loader, model_name=model_name, model=model)
