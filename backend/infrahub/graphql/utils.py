from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Set, Union

from graphene.types.definitions import GrapheneInterfaceType, GrapheneObjectType
from graphql import (  # pylint: disable=no-name-in-module
    ExecutionContext,
    FieldNode,
    FragmentSpreadNode,
    GraphQLList,
    GraphQLObjectType,
    GraphQLResolveInfo,
    GraphQLSchema,
    InlineFragmentNode,
    SelectionSetNode,
)

from infrahub.exceptions import GraphQLQueryError

if TYPE_CHECKING:
    import abc

    from graphql.execution import ExecutionResult


async def extract_fields(selection_set: SelectionSetNode) -> Optional[Dict[str, Dict]]:
    """This function extract all the requested fields in a tree of Dict from a SelectionSetNode

    The goal of this function is to limit the fields that we need to query from the backend.

    Currently the function support Fields and InlineFragments but in a combined tree where the fragments are merged together
    This implementation may seam counter intuitive but in the current implementation
    it's better to have slightly more information at time passed to the query manager.

    In the future we'll probably need to redesign how we read GraphQL queries to generate better Database query.
    """

    if not selection_set:
        return None

    fields = {}
    for node in getattr(selection_set, "selections", []):
        sub_selection_set = getattr(node, "selection_set", None)
        if isinstance(node, FieldNode):
            value = await extract_fields(sub_selection_set)
            if node.name.value not in fields:
                fields[node.name.value] = value
            elif isinstance(fields[node.name.value], dict) and isinstance(value, dict):
                fields[node.name.value].update(value)

        elif isinstance(node, InlineFragmentNode):
            for sub_node in node.selection_set.selections:
                sub_sub_selection_set = getattr(sub_node, "selection_set", None)
                value = await extract_fields(sub_sub_selection_set)
                if sub_node.name.value not in fields:
                    fields[sub_node.name.value] = await extract_fields(sub_sub_selection_set)
                elif isinstance(fields[sub_node.name.value], dict) and isinstance(value, dict):
                    fields[sub_node.name.value].update(value)

    return fields


def extract_data(query_name: str, result: ExecutionResult) -> Dict:
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
) -> List[GrapheneObjectType]:
    results = []
    for _, value in root_schema.type_map.items():
        if not hasattr(value, "interfaces"):
            continue

        for item in value.interfaces:
            if item.name == interface.name:
                results.append(value)

    return results


async def extract_schema_models(fields: dict, schema: GrapheneObjectType, root_schema: GraphQLSchema) -> Set[str]:
    response = set()
    for field_name, value in fields.items():
        if field_name not in schema.fields:
            continue

        if isinstance(schema.fields[field_name].type, GrapheneObjectType):
            object_type = schema.fields[field_name].type
        elif isinstance(schema.fields[field_name].type, GraphQLList):
            object_type = schema.fields[field_name].type.of_type
        elif isinstance(schema.fields[field_name].type, GrapheneInterfaceType):
            object_type = schema.fields[field_name].type
            sub_types = find_types_implementing_interface(interface=object_type, root_schema=root_schema)
            for sub_type in sub_types:
                response.add(sub_type.name)
                response.update(await extract_schema_models(fields=value, schema=sub_type, root_schema=root_schema))
        else:
            continue

        response.add(object_type.name)

        if isinstance(value, dict):
            response.update(await extract_schema_models(fields=value, schema=object_type, root_schema=root_schema))
        elif isinstance(value, str) and value in schema.fields:
            if isinstance(schema.fields[value].type, GrapheneObjectType):
                response.add(schema.fields[value].type.name)
            elif isinstance(schema.fields[value].type, GraphQLList):
                response.add(schema.fields[value].type.of_type.name)

    return response


# --------------------------------------------------------------
# The functions below :
#   - selected_field_names_fast
#   - selected_field_names_naive
#   - selected_field_names
#   - selected_field_names_from_context
# Are not currently used and they have been copied from internet as a reference
#  >>  https://github.com/graphql-python/graphene/issues/57#issuecomment-774227086
#
# --------------------------------------------------------------
def selected_field_names_fast(
    selection_set: SelectionSetNode, context: GraphQLResolveInfo, runtime_type: Union[str, GraphQLObjectType] = None
) -> abc.Iterator[str]:
    """Use the fastest available function to provide the list of selected field names

    Note that this function may give false positives because in the absence of fragments it ignores directives.
    """
    # Any fragments?
    no_fragments = all(isinstance(node, FieldNode) for node in selection_set.selections)

    # Choose the function to execute
    if no_fragments:
        return selected_field_names_naive(selection_set)

    return selected_field_names(selection_set, context, runtime_type)


def selected_field_names_naive(selection_set: SelectionSetNode):
    """Get the list of field names that are selected at the current level. Does not include nested names.

    Limitations:
    * Does not resolve fragments; throws RuntimeError
    * Does not take directives into account. A field might be disabled, and this function wouldn't know

    As a result:
    * It will give a RuntimeError if a fragment is provided
    * It may give false positives in case directives are used
    * It is 20x faster than the alternative

    Benefits:
    * Fast!

    Args:
        selection_set: the selected fields

    Code copied from https://github.com/graphql-python/graphene/issues/57#issuecomment-774227086
        This link also includes a more powerful and complexe alternative.
    """
    assert isinstance(selection_set, SelectionSetNode)

    field_names = []

    for node in selection_set.selections:
        # Field
        if isinstance(node, FieldNode):
            field_names.append(node.name.value)
        # Fragment spread (`... fragmentName`)
        elif isinstance(node, (FragmentSpreadNode, InlineFragmentNode)):
            raise NotImplementedError("Fragments are not supported by this simplistic function")
        # Something new
        else:
            raise NotImplementedError(str(type(node)))

    return field_names


def selected_field_names(
    selection_set: SelectionSetNode, info: GraphQLResolveInfo, runtime_type: Union[str, GraphQLObjectType] = None
) -> abc.Iterator[str]:
    """Get the list of field names that are selected at the current level. Does not include nested names.

    This function re-evaluates the AST, but gives a complete list of included fields.
    It is 25x slower than `selected_field_names_naive()`, but still, it completes in 7ns or so. Not bad.

    Args:
        selection_set: the selected fields
        info: GraphQL resolve info
        runtime_type: The type of the object you resolve to. Either its string name, or its ObjectType.
            If none is provided, this function will fail with a RuntimeError() when resolving fragments
    """
    # pylint: disable=no-value-for-parameter

    # Create a temporary execution context. This operation is quite cheap, actually.
    execution_context = ExecutionContext(
        schema=info.schema,
        fragments=info.fragments,
        root_value=info.root_value,
        operation=info.operation,
        variable_values=info.variable_values,
        # The only purpose of this context is to be able to run the collect_fields() method.
        # Therefore, many parameters are actually irrelevant
        context_value=None,
        field_resolver=None,
        type_resolver=None,
        errors=[],
        middleware_manager=None,
    )

    # Use it
    return selected_field_names_from_context(selection_set, execution_context, runtime_type)


def selected_field_names_from_context(
    selection_set: SelectionSetNode, context: ExecutionContext, runtime_type: Union[str, GraphQLObjectType] = None
) -> abc.Iterator[str]:
    """Get the list of field names that are selected at the current level.

    This function is useless because `graphql.ExecutionContext` is not available at all inside resolvers.
    Therefore, `selected_field_names()` wraps it and provides one.
    """
    assert isinstance(selection_set, SelectionSetNode)

    # Resolve `runtime_type`
    if isinstance(runtime_type, str):
        runtime_type = context.schema.type_map[runtime_type]  # raises: KeyError

    # Resolve all fields
    fields_map = context.collect_fields(
        # Use the provided Object type, or use a dummy object that fails all tests
        runtime_type=runtime_type or None,
        # runtime_type=runtime_type or graphql.GraphQLObjectType('<temp>', []),
        selection_set=selection_set,
        fields={},  # out
        visited_fragment_names=(visited_fragment_names := set()),  # out
    )

    # Test fragment resolution
    if visited_fragment_names and not runtime_type:
        raise RuntimeError(
            "The query contains fragments which cannot be resolved "
            "because `runtime_type` is not provided by the lazy developer"
        )

    # Results!
    return (field.name.value for fields_list in fields_map.values() for field in fields_list)


def print_query(info: GraphQLResolveInfo):
    """Traverse the query"""
    initial_selection_set = info.field_nodes[0].selection_set
    print_selection_set(initial_selection_set, 1)


def print_selection_set(selection_set: SelectionSetNode, level: int = 1) -> int:
    # max_depth = level
    tab = "  "
    for field in getattr(selection_set, "selections", []):
        # print(f"in print_selection_set loop {field}")
        # The field we are at is already a lever deeper, even if it doesn't have its own selection set.
        # max_depth = max(max_depth, level + 1)
        print(f"{level * tab}{field.name.value}")
        if selection_set := getattr(field, "selection_set", None):
            # max_depth = max(max_depth, self._get_query_depth(selection_set, level + 1))
            print_selection_set(selection_set, level + 1)

    # """
    # MATCH (d:Device)
    # WHERE (d)-[]-(:Attribute {name: "name"})-[]-(:AttributeValue {value: "spine1"})
    # MAT36CH (d)-[:IS_RELATED]-(r1:Relationship{type: "device_interface"})-[:IS_RELATED]-(n1)
    # WHERE (n1)-[]-(:Attribute {name: "enabled"})-[]-(:AttributeValue {value: false})
    # OPTIONAL MATCH (d)-[:IS_RELATED]-(r1)-[:IS_RELATED]-(n1)-[:IS_RELATED]-(r2:Relationship {type: "interface_ip"})-[:IS_RELATED]-(n2)
    # RETURN d,n1,r1,n2,r2
    # """
