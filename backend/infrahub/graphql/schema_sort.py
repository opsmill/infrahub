from __future__ import annotations

from typing import TYPE_CHECKING

from graphql.language.ast import (
    DocumentNode,
    EnumTypeDefinitionNode,
    EnumValueDefinitionNode,
    FieldDefinitionNode,
    InputObjectTypeDefinitionNode,
    InputValueDefinitionNode,
    InterfaceTypeDefinitionNode,
    NamedTypeNode,
    ObjectTypeDefinitionNode,
)

if TYPE_CHECKING:
    from graphql import DefinitionNode


def _sort_arguments(args: tuple[InputValueDefinitionNode, ...] | None) -> list[InputValueDefinitionNode] | None:
    """Sort arguments (filters) of a field alphabetically by name.

    Args:
        args: List of input value definition nodes to sort, or None.

    Returns:
        Sorted list of input value definition nodes, or None if input was None.
    """
    if not args:
        return None
    return sorted(args, key=lambda a: a.name.value)


def _sort_fields(fields: tuple[FieldDefinitionNode, ...] | None) -> list[FieldDefinitionNode] | None:
    """Sort fields and their arguments alphabetically.

    Args:
        fields: List of field definition nodes to sort, or None.

    Returns:
        Sorted list of field definition nodes with sorted arguments, or None if input was None.
    """
    if not fields:
        return None
    sorted_fields = []
    for field in sorted(fields, key=lambda fld: fld.name.value):
        sorted_args = _sort_arguments(field.arguments)
        sorted_fields.append(
            FieldDefinitionNode(
                name=field.name,
                type=field.type,
                arguments=sorted_args,
                directives=field.directives,
                description=field.description,
                loc=field.loc,
            )
        )
    return sorted_fields


def _sort_enum_values(values: tuple[EnumValueDefinitionNode, ...] | None) -> list[EnumValueDefinitionNode] | None:
    """Sort enum values alphabetically by name.

    Args:
        values: List of enum value definition nodes to sort, or None.

    Returns:
        Sorted list of enum value definition nodes, or None if input was None.
    """
    if not values:
        return None
    return sorted(values, key=lambda v: v.name.value)


def _sort_input_fields(fields: tuple[InputValueDefinitionNode, ...] | None) -> list[InputValueDefinitionNode] | None:
    """Sort input object fields alphabetically by name.

    Args:
        fields: List of input value definition nodes to sort, or None.

    Returns:
        Sorted list of input value definition nodes, or None if input was None.
    """
    if not fields:
        return None
    return sorted(fields, key=lambda f: f.name.value)


def _sort_interfaces(interfaces: tuple[NamedTypeNode, ...] | None) -> list[NamedTypeNode] | None:
    """Sort interface implementations alphabetically by name.

    Args:
        interfaces: Tuple of named type nodes representing interfaces, or None.

    Returns:
        Sorted list of named type nodes, or None if input was None.
    """
    if not interfaces:
        return None
    return sorted(interfaces, key=lambda i: i.name.value)


def sort_schema_ast(document: DocumentNode) -> DocumentNode:
    """Return a new DocumentNode with all definitions, fields, and arguments sorted alphabetically.

    This function recursively sorts all GraphQL schema elements including:
    - Type definitions (objects, interfaces, enums, input objects)
    - Field definitions and their arguments
    - Enum values
    - Input object fields

    Args:
        document: The GraphQL document node containing schema definitions.

    Returns:
        A new DocumentNode with all elements sorted alphabetically by name.
    """

    sorted_definitions: list[
        ObjectTypeDefinitionNode
        | InterfaceTypeDefinitionNode
        | EnumTypeDefinitionNode
        | InputObjectTypeDefinitionNode
        | DefinitionNode
    ] = []

    for definition in sorted(
        document.definitions, key=lambda d: getattr(d.name, "value", "") if hasattr(d, "name") and d.name else ""
    ):
        if isinstance(definition, (ObjectTypeDefinitionNode, InterfaceTypeDefinitionNode)):
            sorted_fields = _sort_fields(definition.fields)
            sorted_interfaces = _sort_interfaces(definition.interfaces)
            sorted_definitions.append(
                definition.__class__(
                    name=definition.name,
                    interfaces=sorted_interfaces,
                    directives=definition.directives,
                    fields=sorted_fields,
                    description=definition.description,
                    loc=definition.loc,
                )
            )

        elif isinstance(definition, EnumTypeDefinitionNode):
            sorted_values = _sort_enum_values(definition.values)
            sorted_definitions.append(
                EnumTypeDefinitionNode(
                    name=definition.name,
                    directives=definition.directives,
                    values=sorted_values,
                    description=definition.description,
                    loc=definition.loc,
                )
            )
        elif isinstance(definition, InputObjectTypeDefinitionNode):
            sorted_inputs = _sort_input_fields(definition.fields)
            sorted_definitions.append(
                InputObjectTypeDefinitionNode(
                    name=definition.name,
                    directives=definition.directives,
                    fields=sorted_inputs,
                    description=definition.description,
                    loc=definition.loc,
                )
            )
        else:
            sorted_definitions.append(definition)

    return DocumentNode(definitions=sorted_definitions)
