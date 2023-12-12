from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SchemaMappingField(BaseModel):
    name: str
    mapping: Optional[str]
    static: Optional[Any]
    reference: Optional[str]


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
            if hasattr(self, f"load_{item}"):
                print(f"Loading {item}")
                method = getattr(self, f"load_{item}")
                method()
            else:
                print(f"Loading {item}")
                self.model_loader(model_name=item, model=getattr(self, item))

    def model_loader(self, model_name: str, model):
        raise NotImplementedError


class DiffSyncModelMixin:
    @classmethod
    def is_list(cls, name):
        field = cls.__fields__.get(name)
        if not field:
            raise ValueError(f"Unable to find the field {name} under {cls}")

        if isinstance(field.default, list):
            return True

        return False
