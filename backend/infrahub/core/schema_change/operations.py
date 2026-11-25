from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, JsonValue, model_validator

from infrahub.core.schema_change.constants import SCHEMA_CHANGE_NAME_VERSION_DIGITS, SCHEMA_KIND_NAME_PROPERTIES
from infrahub.core.schema_change.enums import SchemaOperationNodeType, SchemaOperationSection, SchemaOperationType

if TYPE_CHECKING:
    from collections.abc import Sequence

ELEMENT_OPERATION_TYPES = frozenset(
    {SchemaOperationType.ELEMENT_ADD, SchemaOperationType.ELEMENT_REMOVE, SchemaOperationType.ELEMENT_PROPERTY}
)
PROPERTY_OPERATION_TYPES = frozenset({SchemaOperationType.NODE_PROPERTY, SchemaOperationType.ELEMENT_PROPERTY})
ADD_OPERATION_TYPES = frozenset({SchemaOperationType.NODE_ADD, SchemaOperationType.ELEMENT_ADD})
REMOVE_OPERATION_TYPES = frozenset({SchemaOperationType.NODE_REMOVE, SchemaOperationType.ELEMENT_REMOVE})

INSTANCE_ID_KEY = "id"
PARAMETERS_KEY = "parameters"
NUMBER_POOL_ID_KEY = "number_pool_id"


@dataclass(frozen=True)
class KindName:
    name: str
    namespace: str

    @property
    def kind(self) -> str:
        return f"{self.namespace}{self.name}"

    def to_value(self) -> dict[str, JsonValue]:
        return {"name": self.name, "namespace": self.namespace}


def read_kind_name(value: JsonValue) -> KindName | None:
    """Return the name and the namespace that the value of a kind rename holds, or `None` when it holds no text for one of them."""
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    namespace = value.get("namespace")
    if not isinstance(name, str) or not isinstance(namespace, str):
        return None
    return KindName(name=name, namespace=namespace)


class SchemaOperation(BaseModel):
    """One change to the schema, naming its target by kind and name.

    A `value` or `previous_value` that was not given is apart from one given as `None` (the JSON
    value `null`): read `has_value` and `has_previous_value`, and dump with `exclude_unset=True`
    to keep the difference through JSON.
    """

    model_config = ConfigDict(extra="forbid")

    operation_type: SchemaOperationType
    kind: str
    """For a renamed kind, the kind before the operation."""

    node_type: SchemaOperationNodeType | None = None
    section: SchemaOperationSection | None = None
    element_name: str | None = None
    """For a renamed attribute or relationship, the name before the operation."""

    property_name: str | None = None
    """Dotted when the property is nested, such as `parameters.regex`."""

    value: JsonValue = None
    """The new value for a property type, the full definition for an add type."""

    previous_value: JsonValue = None

    @property
    def has_value(self) -> bool:
        return "value" in self.model_fields_set

    @property
    def has_previous_value(self) -> bool:
        return "previous_value" in self.model_fields_set

    @model_validator(mode="after")
    def validate_target_fields_match_operation_type(self) -> Self:
        """Require the fields that name the target of the operation type.

        Raises:
            ValueError: If a field that the operation type needs is not set.

        """
        if self.operation_type in ELEMENT_OPERATION_TYPES and (self.section is None or self.element_name is None):
            raise ValueError(f"Operation {self.operation_type.value} requires 'section' and 'element_name'")
        if self.operation_type in PROPERTY_OPERATION_TYPES and self.property_name is None:
            raise ValueError(f"Operation {self.operation_type.value} requires 'property_name'")
        if self.operation_type == SchemaOperationType.NODE_ADD and self.node_type is None:
            raise ValueError(f"Operation {self.operation_type.value} requires 'node_type'")
        if (
            self.operation_type == SchemaOperationType.NODE_PROPERTY
            and self.property_name in SCHEMA_KIND_NAME_PROPERTIES
        ):
            raise ValueError(
                f"Operation {self.operation_type.value} cannot change '{self.property_name}'; use "
                f"{SchemaOperationType.NODE_RENAME.value}"
            )
        if self.operation_type == SchemaOperationType.NODE_RENAME and read_kind_name(self.value) is None:
            raise ValueError(
                f"Operation {self.operation_type.value} requires a value with the text fields "
                f"{' and '.join(repr(name) for name in SCHEMA_KIND_NAME_PROPERTIES)}"
            )
        return self

    @model_validator(mode="after")
    def validate_added_definition_holds_no_instance_id(self) -> Self:
        """Refuse an added definition that holds a value specific to one instance of the schema.

        Raises:
            ValueError: If the definition is not a mapping, or holds `id` or `parameters.number_pool_id`.

        """
        if self.operation_type not in ADD_OPERATION_TYPES:
            return self
        if not isinstance(self.value, dict):
            raise ValueError(f"Operation {self.operation_type.value} requires a definition as its value")

        self._check_definition(definition=self.value, location="")
        if self.operation_type == SchemaOperationType.NODE_ADD:
            for section in SchemaOperationSection:
                elements = self.value.get(section.value)
                if not isinstance(elements, list):
                    continue
                for element in elements:
                    if isinstance(element, dict):
                        self._check_definition(
                            definition=element, location=f" in {section.value} '{element.get('name')}'"
                        )
        return self

    def _check_definition(self, definition: dict[str, JsonValue], location: str) -> None:
        if INSTANCE_ID_KEY in definition:
            raise ValueError(
                f"The value of operation {self.operation_type.value} must not hold '{INSTANCE_ID_KEY}'{location}"
            )
        parameters = definition.get(PARAMETERS_KEY)
        if isinstance(parameters, dict) and NUMBER_POOL_ID_KEY in parameters:
            raise ValueError(
                f"The value of operation {self.operation_type.value} must not hold "
                f"'{PARAMETERS_KEY}.{NUMBER_POOL_ID_KEY}'{location}"
            )


def _summary_action(operation_type: SchemaOperationType) -> str:
    if operation_type in ADD_OPERATION_TYPES:
        return "add"
    if operation_type in REMOVE_OPERATION_TYPES:
        return "remove"
    if operation_type == SchemaOperationType.NODE_RENAME:
        return "rename"
    return "update"


def build_schema_change_summary(*, operations: Sequence[SchemaOperation]) -> str:
    """Build the summary of a schema change from its first operation, with the count of the others.

    Raises:
        ValueError: If `operations` is empty.

    """
    if not operations:
        raise ValueError("A schema change summary needs at least one operation")

    first = operations[0]
    parts = [first.kind.lower()]
    field_name = first.element_name or first.property_name
    if field_name:
        parts.append(field_name)
    parts.append(_summary_action(operation_type=first.operation_type))
    if len(operations) > 1:
        parts.append(f"and_{len(operations) - 1}_more")
    return "_".join(parts)


def build_schema_change_name(*, version: int | None, summary: str) -> str:
    """Build the name of a schema change: its version padded to a fixed width, then its summary."""
    if version is None:
        return summary
    return f"{version:0{SCHEMA_CHANGE_NAME_VERSION_DIGITS}d}_{summary}"
