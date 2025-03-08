from __future__ import annotations

from typing import TYPE_CHECKING

from graphene.types.definitions import GrapheneInterfaceType, GrapheneObjectType
from graphql import (
    GraphQLList,
    GraphQLNonNull,
    GraphQLSchema,
    GraphQLUnionType,
)

from infrahub.exceptions import GraphQLQueryError

if TYPE_CHECKING:
    from graphql.execution import ExecutionResult


def extract_data(query_name: str, result: ExecutionResult) -> dict:
    if result.errors:
        errors = []
        for error in result.errors:
            error_locations = error.locations or []
            errors.append(
                {
                    "message": f"GraphQLQuery {query_name}: {error.message}",
                    "path": error.path,
                    "locations": [{"line": location.line, "column": location.column} for location in error_locations],
                }
            )

        raise GraphQLQueryError(errors=errors)

    return result.data or {}


def find_types_implementing_interface(
    interface: GrapheneInterfaceType, root_schema: GraphQLSchema
) -> list[GrapheneObjectType]:
    results = []
    for value in root_schema.type_map.values():
        if not hasattr(value, "interfaces"):
            continue

        for item in value.interfaces:
            if item.name == interface.name:
                results.append(value)

    return results


async def extract_schema_models(
    fields: dict, schema: GrapheneObjectType | GraphQLUnionType, root_schema: GraphQLSchema
) -> set[str]:
    response = set()

    if isinstance(schema, GraphQLUnionType):
        return {t.name for t in schema.types}

    for field_name, value in fields.items():
        if field_name not in schema.fields:
            continue

        gql_type = schema.fields[field_name].type
        if isinstance(schema.fields[field_name].type, GraphQLNonNull):
            gql_type = schema.fields[field_name].type.of_type

        if isinstance(gql_type, GrapheneObjectType):
            object_type = gql_type
        elif isinstance(gql_type, GraphQLList):
            if isinstance(gql_type.of_type, GraphQLNonNull):
                object_type = gql_type.of_type.of_type
            else:
                object_type = gql_type.of_type
        elif isinstance(gql_type, GrapheneInterfaceType):
            object_type = gql_type
            sub_types = find_types_implementing_interface(interface=object_type, root_schema=root_schema)
            for sub_type in sub_types:
                response.add(sub_type.name)
                response.update(await extract_schema_models(fields=value, schema=sub_type, root_schema=root_schema))
        else:
            continue

        # Ensure that Attribute types are not reported by this function
        if isinstance(object_type, GrapheneObjectType) and object_type.interfaces:
            inherit_from = [intf.name for intf in object_type.interfaces]
            if "AttributeInterface" in inherit_from:
                continue

        if isinstance(object_type, GraphQLNonNull):
            raise ValueError("object_type shouldn't be a of type GraphQLNonNull")

        response.add(object_type.name)

        if isinstance(value, dict):
            response.update(await extract_schema_models(fields=value, schema=object_type, root_schema=root_schema))
        elif isinstance(value, str) and value in schema.fields:
            if isinstance(schema.fields[value].type, GrapheneObjectType):
                response.add(schema.fields[value].type.name)
            elif isinstance(schema.fields[value].type, GraphQLList):
                if isinstance(schema.fields[value].type.of_type, GraphQLNonNull):
                    response.add(schema.fields[value].type.of_type.of_type.name)
                else:
                    response.add(schema.fields[value].type.of_type.name)

    return response
