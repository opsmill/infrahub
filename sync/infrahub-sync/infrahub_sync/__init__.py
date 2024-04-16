from typing import Any, Dict, List, Optional

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]


class SchemaMappingField(pydantic.BaseModel):
    name: str
    mapping: Optional[str] = pydantic.Field(default=None)
    static: Optional[Any] = pydantic.Field(default=None)
    reference: Optional[str] = pydantic.Field(default=None)


class SchemaMappingModel(pydantic.BaseModel):
    name: str
    mapping: str
    identifiers: Optional[List[str]] = pydantic.Field(default=None)
    fields: List[SchemaMappingField] = []


class SyncAdapter(pydantic.BaseModel):
    name: str
    settings: Optional[Dict[str, Any]] = {}


class SyncStore(pydantic.BaseModel):
    type: str
    settings: Optional[Dict[str, Any]] = {}


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
    def is_list(cls, name):
        field = cls.__fields__.get(name)
        if not field:
            raise ValueError(f"Unable to find the field {name} under {cls}")

        if isinstance(field.default, list):
            return True

        return False
