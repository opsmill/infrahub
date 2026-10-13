from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from graphql import GraphQLInterfaceType, GraphQLObjectType, OperationType, get_operation_ast
from graphql.execution.values import get_argument_values, get_variable_values

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.constants.schema import PARENT_CHILD_IDENTIFIER
from infrahub.core.schema import GenericSchema, NodeSchema
from infrahub.graphql.cost.models import CostTreeField, RelationshipRef
from infrahub.graphql.cost.recorder import field_path_from_response_keys

if TYPE_CHECKING:
    from graphql import FieldNode, GraphQLField, GraphQLSchema, OperationDefinitionNode

    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.graphql.analyzer import GraphQLQueryNode, GraphQLQueryReport, InfrahubGraphQLQueryAnalyzer

_HIERARCHY_DIRECTIONS = {"ancestors": RelationshipDirection.OUTBOUND, "descendants": RelationshipDirection.INBOUND}


class _Level(Enum):
    """Where a selection sits inside a field: directly under it, under its edges, or on its nodes."""

    FIELD = auto()
    EDGES = auto()
    NODE = auto()


@dataclass(frozen=True)
class _FieldKey:
    path: str
    kind: str
    relationship_name: str | None


@dataclass
class _FieldBuilder:
    """Selections gathered for one field of the tree, from every place in the query that selects it."""

    path: str
    kind: str
    concrete_kinds: tuple[str, ...]
    relationship: RelationshipRef | None
    cardinality: RelationshipCardinality
    arguments: dict[str, Any]
    max_matching_nodes: int | None
    parent_kinds: set[str] = field(default_factory=set)
    selects_count: bool = False
    attribute_names: set[str] = field(default_factory=set)
    field_names: set[str] = field(default_factory=set)
    edge_names: set[str] = field(default_factory=set)
    node_names: set[str] = field(default_factory=set)
    children: dict[_FieldKey, _FieldBuilder] = field(default_factory=dict)

    def build(self) -> CostTreeField:
        children = tuple(child.build() for child in self.children.values())
        cardinality_one_names = {
            child.relationship.name
            for child in children
            if child.relationship is not None and child.cardinality == RelationshipCardinality.ONE
        }
        return CostTreeField(
            path=self.path,
            kind=self.kind,
            concrete_kinds=self.concrete_kinds,
            parent_kinds=tuple(sorted(self.parent_kinds)),
            relationship=self.relationship,
            cardinality=self.cardinality,
            selected_attribute_count=len(self.attribute_names),
            selected_cardinality_one_count=len(cardinality_one_names),
            selects_count=self.selects_count,
            selects_nodes=self._selects_nodes(),
            id_only=self.cardinality == RelationshipCardinality.ONE
            and self.node_names == {"id"}
            and self.field_names <= {"node", "__typename"},
            max_matching_nodes=self.max_matching_nodes,
            arguments=self.arguments,
            children=children,
        )

    def _selects_nodes(self) -> bool:
        """Follow the resolvers: each returns early, without reading a node, when nothing it reads is selected."""
        if self.cardinality == RelationshipCardinality.ONE:
            return True
        if self.relationship is None:
            return "edges" in self.field_names
        if self.relationship.hierarchical:
            return "node" in self.edge_names
        return bool(self.edge_names & {"node", "properties"})


def build_cost_tree(
    analyzer: InfrahubGraphQLQueryAnalyzer,
    schema: GraphQLSchema,
    schema_branch: SchemaBranch,
    variable_values: dict[str, Any] | None,
) -> list[CostTreeField]:
    """Return the fields of the query operation whose cost can be estimated, merged by path in tree order.

    The tree has the top-level fields that map to a kind, the relationship fields under them, and the
    `ancestors` and `descendants` fields. Nothing below `ancestors` and `descendants` is in the tree, because
    no statistics describe those fields. A mutation or a subscription has no tree.

    Args:
        variable_values: Values of the variables of the operation, or None to read the query without them,
            in which case an argument given by a variable is left out.

    Raises:
        GraphQLError: When a variable value does not match the type the operation declares; the error is the
            first one graphql-core reports.

    """
    operation = get_operation_ast(document_ast=analyzer.document, operation_name=analyzer.operation_name)
    if operation is None or operation.operation != OperationType.QUERY or schema.query_type is None:
        return []

    coerced_variables: dict[str, Any] | None = None
    if variable_values is not None:
        coerced = get_variable_values(
            schema=schema, var_def_nodes=operation.variable_definitions or (), inputs=variable_values
        )
        if isinstance(coerced, list):
            raise coerced[0]
        coerced_variables = coerced

    builder = _CostTreeBuilder(
        schema=schema,
        schema_branch=schema_branch,
        report=analyzer.query_report,
        variable_values=coerced_variables,
    )
    return builder.build(operation=operation)


class _CostTreeBuilder:
    def __init__(
        self,
        schema: GraphQLSchema,
        schema_branch: SchemaBranch,
        report: GraphQLQueryReport,
        variable_values: dict[str, Any] | None,
    ) -> None:
        self.schema = schema
        self.schema_branch = schema_branch
        self.report = report
        self.variable_values = variable_values

    def build(self, operation: OperationDefinitionNode) -> list[CostTreeField]:
        # A document can hold several operations, and only the root fields of this one are read.
        operation_fields = {id(selection) for selection in operation.selection_set.selections}
        top_level: dict[_FieldKey, _FieldBuilder] = {}
        for query in self.report.queries:
            model = query.infrahub_model
            field_node = query.field_node
            response_key = query.response_key
            if model is None or field_node is None or response_key is None or id(field_node) not in operation_fields:
                continue
            self._add_top_level(
                top_level=top_level, query=query, model=model, field_node=field_node, response_key=response_key
            )
        return [top_level_field.build() for top_level_field in top_level.values()]

    def _add_top_level(
        self,
        top_level: dict[_FieldKey, _FieldBuilder],
        query: GraphQLQueryNode,
        model: MainSchemaTypes,
        field_node: FieldNode,
        response_key: str,
    ) -> None:
        keys = (response_key,)
        key = _FieldKey(path=field_path_from_response_keys(keys=keys), kind=model.kind, relationship_name=None)
        builder = top_level.get(key)
        if builder is None:
            arguments = self._arguments(field_definition=self._root_field(field_node=field_node), field_node=field_node)
            builder = _FieldBuilder(
                path=key.path,
                kind=model.kind,
                concrete_kinds=_concrete_kinds(model=model),
                relationship=None,
                cardinality=RelationshipCardinality.MANY,
                arguments=arguments,
                max_matching_nodes=self._max_matching_nodes(query=query, arguments=arguments),
            )
            top_level[key] = builder
        builder.selects_count |= query.selects_count
        self._walk(
            builder=builder,
            node=query,
            keys=keys,
            level=_Level.FIELD,
            model=model,
            node_kinds=frozenset(builder.concrete_kinds),
        )

    def _walk(
        self,
        builder: _FieldBuilder,
        node: GraphQLQueryNode,
        keys: tuple[str, ...],
        level: _Level,
        model: MainSchemaTypes,
        node_kinds: frozenset[str],
    ) -> None:
        """Record the selections under an analyzer node that sits at a level of the field being built.

        Args:
            keys: Response keys from the top-level field to the analyzer node.
            model: Schema of the nodes of the field, or of the inline fragment around the selections.
            node_kinds: Concrete kinds of the nodes the selections apply to.

        """
        for child in node.children:
            field_node = child.field_node
            response_key = child.response_key
            if field_node is None or response_key is None:
                fragment_model = child.infrahub_model
                if level == _Level.NODE and fragment_model is not None:
                    self._walk(
                        builder=builder,
                        node=child,
                        keys=keys,
                        level=level,
                        model=fragment_model,
                        node_kinds=node_kinds.intersection(_concrete_kinds(model=fragment_model)),
                    )
                else:
                    self._walk(builder=builder, node=child, keys=keys, level=level, model=model, node_kinds=node_kinds)
                continue

            child_keys = (*keys, response_key)
            match level:
                case _Level.FIELD:
                    builder.field_names.add(child.path)
                    if child.path == "edges" and builder.cardinality == RelationshipCardinality.MANY:
                        next_level: _Level | None = _Level.EDGES
                    elif child.path == "node" and builder.cardinality == RelationshipCardinality.ONE:
                        next_level = _Level.NODE
                    else:
                        next_level = None
                case _Level.EDGES:
                    builder.edge_names.add(child.path)
                    next_level = _Level.NODE if child.path == "node" else None
                case _Level.NODE:
                    builder.node_names.add(child.path)
                    self._add_node_field(
                        builder=builder,
                        child=child,
                        field_node=field_node,
                        keys=child_keys,
                        model=model,
                        node_kinds=node_kinds,
                    )
                    next_level = None
            if next_level is not None:
                self._walk(
                    builder=builder, node=child, keys=child_keys, level=next_level, model=model, node_kinds=node_kinds
                )

    def _add_node_field(
        self,
        builder: _FieldBuilder,
        child: GraphQLQueryNode,
        field_node: FieldNode,
        keys: tuple[str, ...],
        model: MainSchemaTypes,
        node_kinds: frozenset[str],
    ) -> None:
        relationship = child.relationship
        peer_model = child.infrahub_model
        hierarchy_direction = _HIERARCHY_DIRECTIONS.get(child.path)
        if builder.relationship is not None and builder.relationship.hierarchical:
            if child.path in model.attribute_names:
                builder.attribute_names.add(child.path)
            return
        if relationship is not None and peer_model is not None:
            reference = RelationshipRef(
                identifier=relationship.get_identifier(),
                direction=relationship.direction,
                name=relationship.name,
                hierarchical=False,
            )
            cardinality = relationship.cardinality
        elif hierarchy_direction is not None and (hierarchy_kind := _hierarchy_kind(model=model)) is not None:
            peer_model = self.schema_branch.get(name=hierarchy_kind, duplicate=False)
            reference = RelationshipRef(
                identifier=PARENT_CHILD_IDENTIFIER, direction=hierarchy_direction, name=child.path, hierarchical=True
            )
            cardinality = RelationshipCardinality.MANY
        else:
            if child.path in model.attribute_names:
                builder.attribute_names.add(child.path)
            return

        key = _FieldKey(
            path=field_path_from_response_keys(keys=keys), kind=peer_model.kind, relationship_name=reference.name
        )
        child_builder = builder.children.get(key)
        if child_builder is None:
            child_builder = _FieldBuilder(
                path=key.path,
                kind=peer_model.kind,
                concrete_kinds=_concrete_kinds(model=peer_model),
                relationship=reference,
                cardinality=cardinality,
                arguments=self._arguments(
                    field_definition=self._node_field(model=model, field_node=field_node), field_node=field_node
                ),
                max_matching_nodes=None,
            )
            builder.children[key] = child_builder
        child_builder.parent_kinds.update(node_kinds)
        child_builder.selects_count |= child.selects_count
        self._walk(
            builder=child_builder,
            node=child,
            keys=keys,
            level=_Level.FIELD,
            model=peer_model,
            node_kinds=frozenset(child_builder.concrete_kinds),
        )

    def _root_field(self, field_node: FieldNode) -> GraphQLField:
        query_type = self.schema.query_type
        if query_type is None:
            raise ValueError("The GraphQL schema has no query type")
        return query_type.fields[field_node.name.value]

    def _node_field(self, model: MainSchemaTypes, field_node: FieldNode) -> GraphQLField:
        graphql_type = self.schema.get_type(model.kind)
        if not isinstance(graphql_type, GraphQLObjectType | GraphQLInterfaceType):
            raise TypeError(f"The GraphQL type of {model.kind} is not an object or an interface")
        return graphql_type.fields[field_node.name.value]

    def _arguments(self, field_definition: GraphQLField, field_node: FieldNode) -> dict[str, Any]:
        return get_argument_values(type_def=field_definition, node=field_node, variable_values=self.variable_values)

    def _max_matching_nodes(self, query: GraphQLQueryNode, arguments: dict[str, Any]) -> int | None:
        ids = arguments.get("ids")
        if isinstance(ids, list):
            return len(ids)
        if self.report.query_targets_single_object(query=query):
            return 1
        return None


def _concrete_kinds(model: MainSchemaTypes) -> tuple[str, ...]:
    if isinstance(model, GenericSchema):
        return tuple(model.used_by)
    return (model.kind,)


def _hierarchy_kind(model: MainSchemaTypes) -> str | None:
    if isinstance(model, NodeSchema) and model.hierarchy:
        return model.hierarchy
    if isinstance(model, GenericSchema) and model.hierarchical:
        return model.kind
    return None
