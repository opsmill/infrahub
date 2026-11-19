from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, assert_never

from pydantic import BaseModel, TypeAdapter

from infrahub.core.constants import HashableModelState
from infrahub.core.schema import GenericSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.attribute_schema import get_attribute_schema_class_for_kind
from infrahub.core.schema_change.constants import SCHEMA_ELEMENT_NAME_PROPERTY
from infrahub.core.schema_change.enums import SchemaOperationNodeType, SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.operations import read_kind_name
from infrahub.core.schema_change.schema_elements import find_element, split_property_path
from infrahub.exceptions import SchemaOperationTargetExistsError, SchemaOperationTargetNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic import JsonValue

    from infrahub.core.schema import AttributeSchema, MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.operations import SchemaOperation

ATTRIBUTE_KIND_KEY = "kind"


@dataclass
class _FieldNameChanges:
    """The attribute and relationship names that the operations removed or renamed on one kind, by name before the change."""

    removed: set[str] = field(default_factory=set)
    renamed: dict[str, str] = field(default_factory=dict)
    rename_positions: dict[str, int] = field(default_factory=dict)
    """The position of the operation that renamed each element, by the ID of the element."""

    original_names: dict[str, str] = field(default_factory=dict)
    """The name of each renamed element before the operations, by the ID of the element."""

    def rename(self, element: AttributeSchema | RelationshipSchema, old_name: str, position: int) -> None:
        if element.id is None:
            original_name = self._original_name(name=old_name)
        else:
            original_name = self.original_names.setdefault(element.id, old_name)
            self.rename_positions[element.id] = position
        self.renamed[original_name] = element.name

    def was_renamed(self, element: AttributeSchema | RelationshipSchema) -> bool:
        return element.id is not None and element.id in self.rename_positions

    def remove(self, name: str) -> None:
        original_name = self._original_name(name=name)
        self.renamed.pop(original_name, None)
        self.removed.add(original_name)

    def _original_name(self, name: str) -> str:
        for original_name, new_name in self.renamed.items():
            if new_name == name:
                return original_name
        return name


class SchemaChangeApplier:
    """Applies schema operations to a copy of a schema and processes the result."""

    def apply(
        self,
        *,
        target_schema: SchemaBranch,
        operations: Sequence[SchemaOperation],
        default_branch_schema: SchemaBranch,
    ) -> SchemaBranch:
        """Return a processed copy of `target_schema` with the operations applied in order; `target_schema` is unchanged.

        Raises:
            SchemaOperationTargetNotFoundError: When an operation names a kind, attribute or relationship that the
                schema does not have at that step.
            SchemaOperationTargetExistsError: When an operation adds a kind, or an attribute or relationship of a
                kind, or renames a kind to one that the schema already has at that step, or when a rename leaves two
                attributes or relationships of a kind with the same name after the last operation.

        """
        schema = target_schema.duplicate()
        field_name_changes: dict[str, _FieldNameChanges] = {}
        for position, operation in enumerate(operations):
            self._apply_operation(
                schema=schema, position=position, operation=operation, field_name_changes=field_name_changes
            )

        for kind, changes in field_name_changes.items():
            if not schema.has(name=kind):
                continue
            node = schema.get(name=kind)
            self._refuse_a_rename_onto_a_kept_name(node=node, changes=changes)
            node.apply_schema_path_updates(deleted_field_names=changes.removed, renamed_field_name_map=changes.renamed)
            schema.set(name=kind, schema=node)

        schema.process(default_branch_schema=default_branch_schema)
        return schema

    def _apply_operation(
        self,
        schema: SchemaBranch,
        position: int,
        operation: SchemaOperation,
        field_name_changes: dict[str, _FieldNameChanges],
    ) -> None:
        match operation.operation_type:
            case SchemaOperationType.NODE_ADD:
                added_node = self._build_node(operation=operation)
                if added_node.kind in schema.nodes or added_node.kind in schema.generics:
                    raise SchemaOperationTargetExistsError(
                        position=position, operation_type=operation.operation_type, kind=added_node.kind
                    )
                schema.set(name=added_node.kind, schema=added_node)
            case SchemaOperationType.NODE_REMOVE:
                node = self._get_kind(schema=schema, position=position, operation=operation)
                node.state = HashableModelState.ABSENT
                schema.set(name=operation.kind, schema=node)
            case SchemaOperationType.NODE_PROPERTY:
                node = self._get_kind(schema=schema, position=position, operation=operation)
                self._set_property(
                    holder=node, property_name=self._property_name(operation=operation), value=operation.value
                )
                schema.set(name=operation.kind, schema=node)
            case SchemaOperationType.NODE_RENAME:
                self._rename_kind(
                    schema=schema, position=position, operation=operation, field_name_changes=field_name_changes
                )
            case SchemaOperationType.ELEMENT_ADD:
                node = self._get_kind(schema=schema, position=position, operation=operation)
                self._add_element(node=node, position=position, operation=operation)
                schema.set(name=operation.kind, schema=node)
            case SchemaOperationType.ELEMENT_REMOVE:
                node = self._get_kind(schema=schema, position=position, operation=operation)
                element = self._get_element(
                    node=node, position=position, operation=operation, changes=field_name_changes.get(operation.kind)
                )
                section = self._section(operation=operation)
                if section == SchemaOperationSection.ATTRIBUTES:
                    node.attributes = [item for item in node.attributes if item is not element]
                else:
                    node.relationships = [item for item in node.relationships if item is not element]
                field_name_changes.setdefault(operation.kind, _FieldNameChanges()).remove(name=element.name)
                schema.set(name=operation.kind, schema=node)
            case SchemaOperationType.ELEMENT_PROPERTY:
                node = self._get_kind(schema=schema, position=position, operation=operation)
                element = self._get_element(
                    node=node, position=position, operation=operation, changes=field_name_changes.get(operation.kind)
                )
                property_name = self._property_name(operation=operation)
                name_before = element.name
                self._set_property(holder=element, property_name=property_name, value=operation.value)
                if property_name == SCHEMA_ELEMENT_NAME_PROPERTY and element.name != name_before:
                    field_name_changes.setdefault(operation.kind, _FieldNameChanges()).rename(
                        element=element, old_name=name_before, position=position
                    )
                schema.set(name=operation.kind, schema=node)
            case _ as unreachable:
                assert_never(unreachable)

    def _rename_kind(
        self,
        schema: SchemaBranch,
        position: int,
        operation: SchemaOperation,
        field_name_changes: dict[str, _FieldNameChanges],
    ) -> None:
        node = self._get_kind(schema=schema, position=position, operation=operation)
        kind_name = read_kind_name(operation.value)
        if kind_name is None:
            raise ValueError(f"Operation {operation.operation_type.value} requires a name and a namespace")
        if kind_name.kind != operation.kind and (kind_name.kind in schema.nodes or kind_name.kind in schema.generics):
            raise SchemaOperationTargetExistsError(
                position=position, operation_type=operation.operation_type, kind=kind_name.kind
            )
        node.name = kind_name.name
        node.namespace = kind_name.namespace
        schema.delete(name=operation.kind)
        if operation.kind in field_name_changes:
            field_name_changes[node.kind] = field_name_changes.pop(operation.kind)
        schema.set(name=node.kind, schema=node)

    def _build_node(self, operation: SchemaOperation) -> NodeSchema | GenericSchema:
        if operation.node_type == SchemaOperationNodeType.GENERIC:
            return GenericSchema.model_validate(operation.value)
        return NodeSchema.model_validate(operation.value)

    def _add_element(self, node: NodeSchema | GenericSchema, position: int, operation: SchemaOperation) -> None:
        definition = operation.value
        if not isinstance(definition, dict):
            raise ValueError(f"Operation {operation.operation_type.value} requires a definition as its value")
        section = self._section(operation=operation)
        element_name = self._element_name(operation=operation)
        if find_element(node=node, section=section, name=element_name) is not None:
            raise SchemaOperationTargetExistsError(
                position=position,
                operation_type=operation.operation_type,
                kind=operation.kind,
                section=section,
                element_name=element_name,
            )
        match section:
            case SchemaOperationSection.ATTRIBUTES:
                attribute_kind = definition.get(ATTRIBUTE_KIND_KEY)
                if not isinstance(attribute_kind, str):
                    raise ValueError(
                        f"The attribute definition of operation {operation.operation_type.value} has no kind"
                    )
                attribute_class = get_attribute_schema_class_for_kind(kind=attribute_kind)
                node.attributes.append(attribute_class.model_validate(definition))
            case SchemaOperationSection.RELATIONSHIPS:
                node.relationships.append(RelationshipSchema.model_validate(definition))

    def _get_kind(self, schema: SchemaBranch, position: int, operation: SchemaOperation) -> NodeSchema | GenericSchema:
        if operation.kind not in schema.nodes and operation.kind not in schema.generics:
            raise SchemaOperationTargetNotFoundError(
                position=position, operation_type=operation.operation_type, kind=operation.kind
            )
        return schema.get_node_or_generic_schema(name=operation.kind)

    def _get_element(
        self,
        node: NodeSchema | GenericSchema,
        position: int,
        operation: SchemaOperation,
        changes: _FieldNameChanges | None,
    ) -> AttributeSchema | RelationshipSchema:
        """Return the element that the operation names, preferring one that no earlier operation renamed.

        A rename can give an element the name of another element that a later rename moves away, so the two share
        that name until the later rename.

        Raises:
            SchemaOperationTargetNotFoundError: When the kind has no element with that name in that section.

        """
        section = self._section(operation=operation)
        element_name = self._element_name(operation=operation)
        elements: Sequence[AttributeSchema | RelationshipSchema] = (
            node.attributes if section == SchemaOperationSection.ATTRIBUTES else node.relationships
        )
        named = [item for item in elements if item.name == element_name]
        kept = [item for item in named if changes is None or not changes.was_renamed(item)]
        element = next(iter(kept or named), None)
        if element is None:
            raise SchemaOperationTargetNotFoundError(
                position=position,
                operation_type=operation.operation_type,
                kind=operation.kind,
                section=section,
                element_name=element_name,
            )
        return element

    def _refuse_a_rename_onto_a_kept_name(self, node: MainSchemaTypes, changes: _FieldNameChanges) -> None:
        for section in SchemaOperationSection:
            elements: Sequence[AttributeSchema | RelationshipSchema] = (
                node.attributes if section == SchemaOperationSection.ATTRIBUTES else node.relationships
            )
            names = [element.name for element in elements]
            for element in elements:
                if element.id is None or element.id not in changes.rename_positions or names.count(element.name) < 2:
                    continue
                raise SchemaOperationTargetExistsError(
                    position=changes.rename_positions[element.id],
                    operation_type=SchemaOperationType.ELEMENT_PROPERTY,
                    kind=node.kind,
                    section=section,
                    element_name=element.name,
                )

    def _section(self, operation: SchemaOperation) -> SchemaOperationSection:
        if operation.section is None:
            raise ValueError(f"Operation {operation.operation_type.value} requires 'section'")
        return operation.section

    def _element_name(self, operation: SchemaOperation) -> str:
        if operation.element_name is None:
            raise ValueError(f"Operation {operation.operation_type.value} requires 'element_name'")
        return operation.element_name

    def _property_name(self, operation: SchemaOperation) -> str:
        if operation.property_name is None:
            raise ValueError(f"Operation {operation.operation_type.value} requires 'property_name'")
        return operation.property_name

    def _set_property(self, holder: BaseModel, property_name: str, value: JsonValue) -> None:
        """Set a dotted property path to a JSON value, converted to the type of the field it lands in.

        Raises:
            ValueError: When a level of the path is not a model.

        """
        *parents, field_name = split_property_path(property_name)
        target: object = holder
        for parent in parents:
            target = getattr(target, parent)
        if not isinstance(target, BaseModel) or field_name not in type(target).model_fields:
            raise ValueError(f"Unable to set the property {property_name!r} of {type(holder).__name__}")
        annotation = type(target).model_fields[field_name].annotation
        setattr(target, field_name, TypeAdapter(annotation).validate_python(value))
