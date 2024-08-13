from typing import Any, List, Optional

import pydantic


class SchemaMappingFilter(pydantic.BaseModel):
    field: str
    operation: str
    value: Optional[Any] = None


class SchemaMappingTransform(pydantic.BaseModel):
    field: str
    expression: str


class SchemaMappingField(pydantic.BaseModel):
    name: str
    mapping: Optional[str] = pydantic.Field(default=None)
    static: Optional[Any] = pydantic.Field(default=None)
    reference: Optional[str] = pydantic.Field(default=None)


class SchemaMappingModel(pydantic.BaseModel):
    name: str
    mapping: str
    identifiers: Optional[List[str]] = pydantic.Field(default=None)
    filters: Optional[List[SchemaMappingFilter]] = pydantic.Field(default=None)
    transforms: Optional[List[SchemaMappingTransform]] = pydantic.Field(default=None)
    fields: List[SchemaMappingField] = []


class SyncAdapter(pydantic.BaseModel):
    name: str
    settings: Optional[dict[str, Any]] = {}


class SyncStore(pydantic.BaseModel):
    type: str
    settings: Optional[dict[str, Any]] = {}


class SyncConfig(pydantic.BaseModel):
    name: str
    store: Optional[SyncStore] = []
    source: SyncAdapter
    destination: SyncAdapter
    order: List[str] = pydantic.Field(default_factory=list)
    schema_mapping: List[SchemaMappingModel] = []


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
    def get_resource_name(cls, schema_mapping):
        """Get the resource name from the schema mapping."""
        for element in schema_mapping:
            if element.name == cls.__name__:
                return element.mapping
        raise ValueError(f"Resource name not found for class {cls.__name__}")

    @classmethod
    def is_list(cls, name):
        field = cls.__fields__.get(name)
        if not field:
            raise ValueError(f"Unable to find the field {name} under {cls}")

        if isinstance(field.default, list):
            return True

        return False
