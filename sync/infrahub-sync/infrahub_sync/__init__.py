import operator
import re
from typing import Any, List, Optional, Union

import pydantic
from jinja2 import Template
from netutils.ip import is_ip_within as netutils_is_ip_within

from infrahub_sync.adapters.utils import get_value


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


def is_ip_within_filter(ip: str, ip_compare: Union[str, List[str]]) -> bool:
    """Check if an IP address is within a given subnet."""
    return netutils_is_ip_within(ip=ip, ip_compare=ip_compare)


def convert_to_int(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Cannot convert '{value}' to int") from exc


FILTERS_OPERATIONS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": lambda field, value: operator.gt(convert_to_int(field), convert_to_int(value)),
    "<": lambda field, value: operator.lt(convert_to_int(field), convert_to_int(value)),
    ">=": lambda field, value: operator.ge(convert_to_int(field), convert_to_int(value)),
    "<=": lambda field, value: operator.le(convert_to_int(field), convert_to_int(value)),
    "in": lambda field, value: value and field in value,
    "not in": lambda field, value: field not in value,
    "contains": lambda field, value: field and value in field,
    "not contains": lambda field, value: field and value not in field,
    "is_empty": lambda field: field is None or not field,
    "is_not_empty": lambda field: field is not None and field,
    "regex": lambda field, pattern: re.match(pattern, field) is not None,
    # Netutils
    "is_ip_within": lambda field, value: is_ip_within_filter(ip=field, ip_compare=value),
}


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
    def apply_filter(cls, field_value: Any, operation: str, value: Any) -> bool:
        """Apply a specified operation to a field value."""
        operation_func = FILTERS_OPERATIONS.get(operation)
        if operation_func is None:
            raise ValueError(f"Unsupported operation: {operation}")

        # Handle is_empty and is_not_empty which do not use the value argument
        if operation in {"is_empty", "is_not_empty"}:
            return operation_func(field_value)

        return operation_func(field_value, value)

    @classmethod
    def apply_filters(cls, item: dict[str, Any], filters: List[SchemaMappingFilter]) -> bool:
        """Apply filters to an item and return True if it passes all filters."""
        for filter_obj in filters:
            # Use dot notation to access attributes
            field_value = get_value(obj=item, name=filter_obj.field)
            if not cls.apply_filter(field_value=field_value, operation=filter_obj.operation, value=filter_obj.value):
                return False
        return True

    @classmethod
    def apply_transform(cls, item: dict[str, Any], transform_expr: str, field: str) -> None:
        """Apply a transformation expression using Jinja2 to a specified field in the item."""
        try:
            # Create a Jinja2 template from the transformation expression
            template = Template(transform_expr)

            # Render the template using the item's context
            transformed_value = template.render(**item)

            # Assign the result back to the item
            item[field] = transformed_value
        except Exception as exc:
            raise ValueError(f"Failed to transform '{field}' with '{transform_expr}': {exc}") from exc

    @classmethod
    def apply_transforms(cls, item: dict[str, Any], transforms: List[SchemaMappingTransform]) -> dict[str, Any]:
        """Apply a list of structured transformations to an item."""
        for transform_obj in transforms:
            field = transform_obj.field
            expr = transform_obj.expression
            cls.apply_transform(item=item, transform_expr=expr, field=field)
        return item

    @classmethod
    def filter_records(cls, records: list[dict], schema_mapping: SchemaMappingModel) -> list[dict]:
        """
        Apply filters to the records based on the schema mapping configuration.
        """
        filters = schema_mapping.filters or []
        if not filters:
            return records
        filtered_records = []
        for record in records:
            if cls.apply_filters(item=record, filters=filters):
                filtered_records.append(record)
        return filtered_records

    @classmethod
    def transform_records(cls, records: list[dict], schema_mapping: SchemaMappingModel) -> list[dict]:
        """
        Apply transformations to the records based on the schema mapping configuration.
        """
        transforms = schema_mapping.transforms or []
        if not transforms:
            return records
        transformed_records = []
        for record in records:
            transformed_record = cls.apply_transforms(item=record, transforms=transforms)
            transformed_records.append(transformed_record)
        return transformed_records

    @classmethod
    def get_resource_name(cls, schema_mapping: List[SchemaMappingModel]) -> str:
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
