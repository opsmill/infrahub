from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, Any

from graphql import (
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    GraphQLSchema,
    InlineFragmentNode,
    NamedTypeNode,
    NonNullTypeNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
)
from infrahub_sdk.analyzer import GraphQLQueryAnalyzer
from infrahub_sdk.utils import extract_fields

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import GenericSchema, NodeSchema
from infrahub.graphql.utils import extract_schema_models

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch


class ContextType(str, Enum):
    EDGE = "edge"
    NODE = "node"
    DIRECT = "direct"
    OBJECT = "object"

    @classmethod
    def from_operation(cls, operation: OperationType) -> ContextType:
        match operation:
            case OperationType.QUERY:
                return cls.EDGE
            case OperationType.MUTATION:
                return cls.OBJECT
            case OperationType.SUBSCRIPTION:
                return cls.EDGE

    @classmethod
    def from_relationship_cardinality(cls, cardinality: RelationshipCardinality) -> ContextType:
        match cardinality:
            case RelationshipCardinality.MANY:
                return cls.EDGE
            case RelationshipCardinality.ONE:
                return cls.NODE


class GraphQLOperation(str, Enum):
    QUERY = "query"
    MUTATION = "mutation"
    SUBSCRIPTION = "subscription"
    UNDEFINED = "undefined"

    @classmethod
    def from_operation(cls, operation: OperationType) -> GraphQLOperation:
        match operation:
            case OperationType.QUERY:
                return cls.QUERY
            case OperationType.MUTATION:
                return cls.MUTATION
            case OperationType.SUBSCRIPTION:
                return cls.SUBSCRIPTION


@dataclass
class GraphQLSelectionSet:
    field_nodes: list[FieldNode]
    fragment_spread_nodes: list[FragmentSpreadNode]
    inline_fragment_nodes: list[InlineFragmentNode]


@dataclass
class GraphQLArgument:
    name: str
    value: str
    kind: str


@dataclass
class ObjectAccess:
    attributes: set[str] = field(default_factory=set)
    relationships: set[str] = field(default_factory=set)


@dataclass
class GraphQLVariable:
    name: str
    type: str
    required: bool


@dataclass
class GraphQLQueryModel:
    model: MainSchemaTypes
    root: bool
    arguments: list[GraphQLArgument]
    attributes: set[str]
    relationships: set[str]


@dataclass
class GraphQLQueryNode:
    path: str
    operation: GraphQLOperation = field(default=GraphQLOperation.UNDEFINED)
    arguments: list[GraphQLArgument] = field(default_factory=list)
    variables: list[GraphQLVariable] = field(default_factory=list)
    context_type: ContextType = field(default=ContextType.EDGE)
    parent: GraphQLQueryNode | None = field(default=None)
    children: list[GraphQLQueryNode] = field(default_factory=list)
    infrahub_model: MainSchemaTypes | None = field(default=None)
    infrahub_node_models: list[NodeSchema] = field(default_factory=list)
    infrahub_attributes: set[str] = field(default_factory=set)
    infrahub_relationships: set[str] = field(default_factory=set)
    field_node: FieldNode | None = field(default=None)

    def context_model(self) -> MainSchemaTypes | None:
        """Return the closest Infrahub object by going up in the tree"""
        if self.infrahub_model:
            return self.infrahub_model
        if self.parent:
            return self.parent.context_model()

        return None

    def context_path(self) -> str:
        """Return the relative path for the current context with the closest Infrahub object as the root"""
        if self.infrahub_model:
            return f"/{self.path}"
        if self.parent:
            return f"{self.parent.context_path()}/{self.path}"
        return self.path

    def properties_path(self) -> str:
        """Indicate the expected path to where Infrahub attributes and relationships would be defined."""
        if self.infrahub_model:
            match self.context_type:
                case ContextType.DIRECT:
                    return f"/{self.path}"
                case ContextType.EDGE:
                    return f"/{self.path}/edges/node"
                case ContextType.NODE:
                    return f"/{self.path}/node"
                case ContextType.OBJECT:
                    return f"/{self.path}/object"
        if self.parent:
            return self.parent.properties_path()

        return self.path

    def full_path(self) -> str:
        """Return the full path within the tree for the current context."""
        if self.parent:
            return f"{self.parent.full_path()}/{self.path}"
        return self.path

    @property
    def at_root(self) -> bool:
        if self.parent:
            return True
        return False

    @property
    def in_property_level(self) -> bool:
        """Indicate if properties, i.e., attributes and relationships could exist at this level."""
        return self.context_path() == self.properties_path()

    def append_attribute(self, attribute: str) -> None:
        """Add attributes to the closes parent Infrahub object."""
        if self.infrahub_model:
            self.infrahub_attributes.add(attribute)
        elif self.parent:
            self.parent.append_attribute(attribute=attribute)

    def append_relationship(self, relationship: str) -> None:
        """Add relationships to the closes parent Infrahub object."""
        if self.infrahub_model:
            self.infrahub_relationships.add(relationship)
        elif self.parent:
            self.parent.append_relationship(relationship=relationship)

    def get_models(self) -> list[GraphQLQueryModel]:
        """Return all models defined on this node along with child nodes"""
        models: list[GraphQLQueryModel] = []
        if self.infrahub_model:
            models.append(
                GraphQLQueryModel(
                    model=self.infrahub_model,
                    root=self.at_root,
                    arguments=self.arguments,
                    attributes=self.infrahub_attributes,
                    relationships=self.infrahub_relationships,
                )
            )
            for used_by in self.infrahub_node_models:
                models.append(
                    GraphQLQueryModel(
                        model=used_by,
                        root=self.at_root,
                        arguments=self.arguments,
                        attributes=self.infrahub_attributes,
                        relationships=self.infrahub_relationships,
                    )
                )

        for child in self.children:
            models.extend(child.get_models())
        return models


@dataclass
class GraphQLQueryReport:
    queries: list[GraphQLQueryNode]

    @property
    def impacted_models(self) -> list[str]:
        """Return a list of all Infrahub objects that are impacted by queries within the request"""
        models: set[str] = set()
        for query in self.queries:
            query_models = query.get_models()
            models.update([query_model.model.kind for query_model in query_models])

        return sorted(models)

    @property
    def requested_read(self) -> dict[str, ObjectAccess]:
        """Return Infrahub objects and the fields (attributes and relationships) that this query would attempt to read"""
        access: dict[str, ObjectAccess] = {}
        for query in self.queries:
            query_models = query.get_models()
            for query_model in query_models:
                if query_model.model.kind not in access:
                    access[query_model.model.kind] = ObjectAccess()
                access[query_model.model.kind].attributes.update(query_model.attributes)
                access[query_model.model.kind].relationships.update(query_model.relationships)

        return access


class InfrahubGraphQLQueryAnalyzer(GraphQLQueryAnalyzer):
    def __init__(
        self,
        query: str,
        branch: Branch,
        schema_branch: SchemaBranch,
        schema: GraphQLSchema | None = None,
        query_variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> None:
        self.branch = branch
        self.schema_branch = schema_branch
        self.operation_name = operation_name
        self.query_variables: dict[str, Any] = query_variables or {}
        self._named_fragments: dict[str, GraphQLQueryNode] = {}
        super().__init__(query=query, schema=schema)

    @property
    def operation_names(self) -> list[str]:
        return [operation.name for operation in self.operations if operation.name is not None]

    @cached_property
    def _fragment_definitions(self) -> list[FragmentDefinitionNode]:
        return [
            definition for definition in self.document.definitions if isinstance(definition, FragmentDefinitionNode)
        ]

    @cached_property
    def _operation_definitions(self) -> list[OperationDefinitionNode]:
        return [
            definition for definition in self.document.definitions if isinstance(definition, OperationDefinitionNode)
        ]

    def get_named_fragment_with_parent(self, name: str, parent: GraphQLQueryNode) -> GraphQLQueryNode:
        """Return a copy of the named fragment and attach it to a parent.

        We return a copy of the object as a named fragment could be used by multiple queries and as we're
        generally working with references to objects we wouldn't want to override the parent of a previously
        assigned object
        """
        named_fragment = deepcopy(self._named_fragments[name])
        named_fragment.parent = parent
        return named_fragment

    async def get_models_in_use(self, types: dict[str, Any]) -> set[str]:
        """List of Infrahub models that are referenced in the query."""
        graphql_types = set()
        models = set()

        if not self.schema:
            raise ValueError("Schema must be provided to extract the models in use.")

        for definition in self.document.definitions:
            fields = await extract_fields(definition.selection_set)

            operation = getattr(definition, "operation", None)
            if operation == OperationType.QUERY:
                schema = self.schema.query_type
            elif operation == OperationType.MUTATION:
                schema = self.schema.mutation_type
            else:
                # Subscription not supported right now
                continue

            graphql_types.update(await extract_schema_models(fields=fields, schema=schema, root_schema=self.schema))

        for graphql_type_name in graphql_types:
            try:
                graphql_type = types.get(graphql_type_name)
                if not hasattr(graphql_type, "_meta") or not hasattr(graphql_type._meta, "schema"):  # type: ignore[union-attr]
                    continue
                models.add(graphql_type._meta.schema.kind)  # type: ignore[union-attr]
            except ValueError:
                continue

        return models

    @cached_property
    def query_report(self) -> GraphQLQueryReport:
        self._populate_named_fragments()
        operations = self._get_operations()

        return GraphQLQueryReport(queries=operations)

    def _get_operations(self) -> list[GraphQLQueryNode]:
        operations: list[GraphQLQueryNode] = []
        for operation_definition in self._operation_definitions:
            selections = self._get_selections(selection_set=operation_definition.selection_set)

            for field_node in selections.field_nodes:
                schema_model: MainSchemaTypes
                infrahub_node_models: list[NodeSchema] = []
                model_name = self._get_model_name(node=field_node, operation_definition=operation_definition)

                if model_name in self.schema_branch.node_names:
                    schema_model = self.schema_branch.get_node(name=model_name, duplicate=False)
                elif model_name in self.schema_branch.generic_names:
                    schema_model = self.schema_branch.get_generic(name=model_name, duplicate=False)
                    infrahub_node_models = [
                        self.schema_branch.get_node(name=used_by, duplicate=False) for used_by in schema_model.used_by
                    ]
                elif model_name in self.schema_branch.profile_names:
                    schema_model = self.schema_branch.get_profile(name=model_name, duplicate=False)
                else:
                    continue

                operational_node = GraphQLQueryNode(
                    operation=GraphQLOperation.from_operation(operation=operation_definition.operation),
                    path=schema_model.kind,
                    infrahub_model=schema_model,
                    infrahub_node_models=infrahub_node_models,
                    context_type=ContextType.from_operation(operation=operation_definition.operation),
                    arguments=self._parse_arguments(field_node=field_node),
                    variables=self._get_variables(operation=operation_definition),
                )

                if field_node.selection_set:
                    selections = self._get_selections(selection_set=field_node.selection_set)
                    for selection_field_node in selections.field_nodes:
                        operational_node.children.append(
                            self._populate_field_node(node=selection_field_node, query_node=operational_node)
                        )
                operations.append(operational_node)
        return operations

    @staticmethod
    def _get_model_name(node: FieldNode, operation_definition: OperationDefinitionNode) -> str:
        if operation_definition.operation == OperationType.MUTATION:
            if node.name.value.endswith("Create"):
                return node.name.value[:-6]
            if node.name.value.endswith("Delete"):
                return node.name.value[:-6]
            if node.name.value.endswith("Update"):
                return node.name.value[:-6]
            if node.name.value.endswith("Upsert"):
                return node.name.value[:-6]
        return node.name.value

    def _populate_named_fragments(self) -> None:
        self._named_fragments = {}
        for fragment_definition in self._fragment_definitions:
            fragment_name = fragment_definition.name.value
            condition_name = fragment_definition.type_condition.name.value
            selections = self._get_selections(selection_set=fragment_definition.selection_set)

            infrahub_model = self.schema_branch.get(name=condition_name, duplicate=False)

            named_fragment = GraphQLQueryNode(
                path=fragment_definition.type_condition.name.value,
                context_type=ContextType.DIRECT,
                infrahub_model=infrahub_model,
            )
            for field_node in selections.field_nodes:
                named_fragment.children.append(self._populate_field_node(node=field_node, query_node=named_fragment))
            for inline_fragment_node in selections.inline_fragment_nodes:
                named_fragment.children.append(
                    self._populate_inline_fragment_node(node=inline_fragment_node, query_node=named_fragment)
                )

            self._named_fragments[fragment_name] = named_fragment

    def _populate_field_node(self, node: FieldNode, query_node: GraphQLQueryNode) -> GraphQLQueryNode:
        context_type = query_node.context_type
        infrahub_model = None
        infrahub_node_models: list[NodeSchema] = []
        if query_node.in_property_level:
            if model := query_node.context_model():
                if node.name.value in model.attribute_names:
                    query_node.append_attribute(attribute=node.name.value)
                elif node.name.value in model.relationship_names:
                    rel = model.get_relationship_or_none(name=node.name.value)
                    if rel:
                        infrahub_model = self.schema_branch.get(name=rel.peer, duplicate=False)
                        if isinstance(infrahub_model, GenericSchema):
                            infrahub_node_models = [
                                self.schema_branch.get_node(name=used_by, duplicate=False)
                                for used_by in infrahub_model.used_by
                            ]

                        context_type = ContextType.from_relationship_cardinality(cardinality=rel.cardinality)
                    query_node.append_relationship(relationship=node.name.value)

        current_node = GraphQLQueryNode(
            parent=query_node,
            path=node.name.value,
            context_type=context_type,
            infrahub_model=infrahub_model,
            infrahub_node_models=infrahub_node_models,
            arguments=self._parse_arguments(field_node=node),
        )

        if node.selection_set:
            selections = self._get_selections(selection_set=node.selection_set)
            for field_node in selections.field_nodes:
                current_node.children.append(self._populate_field_node(node=field_node, query_node=current_node))
            for inline_fragment_node in selections.inline_fragment_nodes:
                current_node.children.append(
                    self._populate_inline_fragment_node(node=inline_fragment_node, query_node=current_node)
                )
            for fragment_spread_node in selections.fragment_spread_nodes:
                current_node.children.append(
                    self._populate_fragment_spread_node(node=fragment_spread_node, query_node=current_node)
                )

        return current_node

    def _populate_inline_fragment_node(
        self, node: InlineFragmentNode, query_node: GraphQLQueryNode
    ) -> GraphQLQueryNode:
        context_type = query_node.context_type
        infrahub_model = self.schema_branch.get(name=node.type_condition.name.value)
        context_type = ContextType.DIRECT
        current_node = GraphQLQueryNode(
            parent=query_node,
            path=node.type_condition.name.value,
            context_type=context_type,
            infrahub_model=infrahub_model,
        )
        if node.selection_set:
            selections = self._get_selections(selection_set=node.selection_set)
            for field_node in selections.field_nodes:
                current_node.children.append(self._populate_field_node(node=field_node, query_node=current_node))
            for inline_fragment_node in selections.inline_fragment_nodes:
                current_node.children.append(
                    self._populate_inline_fragment_node(node=inline_fragment_node, query_node=current_node)
                )

        return current_node

    def _populate_fragment_spread_node(
        self, node: FragmentSpreadNode, query_node: GraphQLQueryNode
    ) -> GraphQLQueryNode:
        return self.get_named_fragment_with_parent(name=node.name.value, parent=query_node)

    @staticmethod
    def _get_selections(selection_set: SelectionSetNode) -> GraphQLSelectionSet:
        return GraphQLSelectionSet(
            field_nodes=[selection for selection in selection_set.selections if isinstance(selection, FieldNode)],
            fragment_spread_nodes=[
                selection for selection in selection_set.selections if isinstance(selection, FragmentSpreadNode)
            ],
            inline_fragment_nodes=[
                selection for selection in selection_set.selections if isinstance(selection, InlineFragmentNode)
            ],
        )

    @staticmethod
    def _get_variables(operation: OperationDefinitionNode) -> list[GraphQLVariable]:
        variables = []
        for variable in operation.variable_definitions:
            if isinstance(variable.type, NamedTypeNode):
                variables.append(
                    GraphQLVariable(name=variable.variable.name.value, type=variable.type.name.value, required=False)
                )
            elif isinstance(variable.type, NonNullTypeNode):
                if isinstance(variable.type.type, NamedTypeNode):
                    variables.append(
                        GraphQLVariable(
                            name=variable.variable.name.value, type=variable.type.type.name.value, required=True
                        )
                    )

        return variables

    @staticmethod
    def _parse_arguments(field_node: FieldNode) -> list[GraphQLArgument]:
        return [
            GraphQLArgument(
                name=argument.name.value,
                value=getattr(argument.value, "value", ""),
                kind=argument.value.kind,
            )
            for argument in field_node.arguments
        ]
