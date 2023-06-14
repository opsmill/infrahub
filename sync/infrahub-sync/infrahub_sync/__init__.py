import functools
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SchemaMappingField(BaseModel):
    name: str
    mapping: Optional[str]
    static: Optional[Any]


class SchemaMappingModel(BaseModel):
    name: str
    mapping: str
    identifiers: Optional[List[str]]
    fields: List[SchemaMappingField]


class SyncAdapter(BaseModel):
    name: str
    settings: Optional[Dict[str, Any]]


class SyncConfig(BaseModel):
    name: str
    source: SyncAdapter
    destination: SyncAdapter
    order: List[str]
    schema_mapping: List[SchemaMappingModel]


class SyncInstance(SyncConfig):
    directory: str


class DiffSyncMixin:
    def load(self):
        """Load all the models, one by one based on the order defined in top_level."""
        for item in self.top_level:
            try:
                method = getattr(self, f"load_{item}")
                method()
            except AttributeError:
                pass

    def model_loader(self, model_name: str, model):
        raise NotImplementedError

    def __getattr__(self, item: str):
        """Intercept all load_<modelname> method and redirect them to the default model_loader"""
        if not item.startswith("load_"):
            raise AttributeError

        model_name = item.replace("load_", "")

        if not hasattr(self, model_name):
            raise AttributeError(f"Unable to find the model {model_name}")

        model = getattr(self, model_name)
        return functools.partial(self.model_loader, model_name=model_name, model=model)
