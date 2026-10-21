from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cached_property
from typing import TYPE_CHECKING, Any

from graphql import (
    DocumentNode,
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    GraphQLSchema,
    InlineFragmentNode,
    ListTypeNode,
    NamedTypeNode,
    NonNullTypeNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
    TypeNode,
)
from graphql.language.ast import (
    BooleanValueNode,
    ConstListValueNode,
    ConstObjectValueNode,
    EnumValueNode,
    FloatValueNode,
    IntValueNode,
    ListValueNode,
    NullValueNode,
    ObjectValueNode,
    StringValueNode,
    ValueNode,
    VariableNode,
)
from infrahub_sdk.analyzer import GraphQLQueryAnalyzer
from infrahub_sdk.utils import extract_fields

from infrahub.core.constants import RESERVED_ATTR_REL_HIERARCHICAL_NAMES, RelationshipCardinality
from infrahub.core.regeneration.models import FilterLiteral, PeerFilters, ReachedPath, RelationshipHop, RelationshipRead
from infrahub.core.schema import AttributePathParsingError, GenericSchema
from infrahub.exceptions import SchemaNotFoundError
from infrahub.graphql.resolvers.peer_filters import build_peer_filters
from infrahub.graphql.utils import extract_schema_models

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes, SchemaAttributePath
    from infrahub.core.schema.schema_branch import SchemaBranch

# Selectable like attributes but absent from a model's attribute list. Values are the schema names.
NODE_PROPERTY_BY_QUERY_FIELD = {"display_label": "display_label", "hfid": "human_friendly_id"}


class MutateAction(StrEnum):
    CREATE = "create"
    DELETE = "delete"
    UPDATE = "update"


class ContextType(StrEnum):
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


class GraphQLOperation(StrEnum):
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
    """An argument of a field in a query, as written: its name and the value node the parser read."""

    name: str
    value_node: ValueNode

    @cached_property
    def value(self) -> Any:
        """The Python value of the literal; a variable reads as its ``$``-prefixed name."""
        return _parse_value_node(self.value_node)

    @property
    def kind(self) -> str:
        """The graphql-core kind of the value node, such as ``variable`` or ``list_value``."""
        return self.value_node.kind

    @property
    def contains_variable(self) -> bool:
        """Whether the value holds a variable, also inside a list or an object."""
        return _contains_value_node(self.value_node, VariableNode)

    @property
    def contains_enum_value(self) -> bool:
        """Whether the value holds an enum name, also inside a list or an object."""
        return _contains_value_node(self.value_node, EnumValueNode)

    @property
    def is_variable(self) -> bool:
        return self.kind == "variable"

    @property
    def as_variable_name(self) -> str:
        """Return the name without a $ prefix."""
        return str(self.value).removeprefix("$")

    @property
    def fields(self) -> list[str]:
        if self.kind != "object_value" or not isinstance(self.value, dict):
            return []
        return sorted(self.value.keys())


@dataclass
class ObjectAccess:
    attributes: set[str] = field(default_factory=set)
    relationships: set[str] = field(default_factory=set)

    @property
    def fields(self) -> set[str]:
        return self.attributes.union(self.relationships)


@dataclass
class GraphQLVariable:
    name: str
    type: str
    required: bool
    is_list: bool = False
    inner_required: bool = False
    default: Any | None = None


@dataclass
class GraphQLQueryModel:
    model: MainSchemaTypes
    root: bool
    arguments: list[GraphQLArgument]
    attributes: set[str]
    relationships: set[str]
    mutate_actions: list[MutateAction] = field(default_factory=list)


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
    infrahub_node_models: list[MainSchemaTypes] = field(default_factory=list)
    infrahub_attributes: set[str] = field(default_factory=set)
    infrahub_relationships: set[str] = field(default_factory=set)
    field_node: FieldNode | None = field(default=None)
    mutate_actions: list[MutateAction] = field(default_factory=list)
    is_fragment: bool = field(default=False)

    def context_model(self) -> MainSchemaTypes | None:
        """Return the closest Infrahub object by going up in the tree."""
        if self.infrahub_model:
            return self.infrahub_model
        if self.parent:
            return self.parent.context_model()

        return None

    def context_path(self) -> str:
        """Return the relative path for the current context with the closest Infrahub object as the root."""
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
            return False
        return True

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
        """Return all models defined on this node along with child nodes."""
        models: list[GraphQLQueryModel] = []
        if self.infrahub_model:
            models.append(
                GraphQLQueryModel(
                    model=self.infrahub_model,
                    root=self.at_root,
                    arguments=self.arguments,
                    attributes=self.infrahub_attributes,
                    relationships=self.infrahub_relationships,
                    mutate_actions=self.mutate_actions,
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
                        mutate_actions=self.mutate_actions,
                    )
                )

        for child in self.children:
            models.extend(child.get_models())
        return models


def _reached_path_sort_key(path: ReachedPath) -> tuple[tuple[str, str, str, str], ...]:
    """Order paths by their hops, filters included, so paths that differ only by their filters sort in a fixed order."""
    return tuple(
        (hop.node_kind, hop.relationship_identifier, hop.relationship_direction.value, repr(hop.peer_filters))
        for hop in path.hops
    )


def _peer_filters(node: GraphQLQueryNode) -> PeerFilters | None:
    """Return the filters a relationship read passes to the peer query, from its constant arguments.

    Variables and enum names are left out because the query text does not hold their value, and ``display_label``
    and ``hfid`` filters because their value depends on other nodes. Leaving a filter out can only select more
    targets, never fewer.
    """
    arguments = {
        argument.name: literal
        for argument in node.arguments
        if not argument.contains_variable
        and not argument.contains_enum_value
        and argument.name.partition("__")[0] not in NODE_PROPERTY_BY_QUERY_FIELD
        and (literal := _filter_literal(argument.value)) is not None
    }
    filters = build_peer_filters(field_name=node.path, arguments=arguments)
    if not filters:
        return None
    return PeerFilters(relationship_name=node.path, filters=tuple(sorted(filters.items())))


def _filter_literal(value: Any) -> FilterLiteral | None:
    """Return a constant argument value as a filter value, or None for a value the peer query rejects."""
    if isinstance(value, str | int):
        return value
    if isinstance(value, list) and all(isinstance(item, str | int) for item in value):
        return tuple(value)
    return None


def _reads_peers_another_way(node: GraphQLQueryNode) -> bool:
    """Whether a node selects peers by something other than the peers' own fields.

    This covers a filter on a field of a related node, such as ``owner__name__value``, and a hierarchy read
    (``descendants``, ``ancestors``, ``include_descendants``).
    """
    if node.path in RESERVED_ATTR_REL_HIERARCHICAL_NAMES:
        return True
    model = node.infrahub_model
    for argument in node.arguments:
        if argument.name == "include_descendants" and (argument.contains_variable or argument.value):
            return True
        field_name, separator, rest = argument.name.partition("__")
        if model is not None and separator and "__" in rest and model.get_relationship_or_none(name=field_name):
            return True
    return False


def _iter_nodes(node: GraphQLQueryNode) -> Iterator[GraphQLQueryNode]:
    """Yield every node of the subtree, including nodes without a model such as hierarchy fields."""
    yield node
    for child in node.children:
        yield from _iter_nodes(child)


def _contains_value_node(node: ValueNode, node_type: type[ValueNode]) -> bool:
    """Whether a value node is of ``node_type`` or contains one in a list or an object."""
    match node:
        case _ if isinstance(node, node_type):
            return True
        case ListValueNode() | ConstListValueNode():
            return any(_contains_value_node(item, node_type) for item in node.values)
        case ObjectValueNode() | ConstObjectValueNode():
            return any(_contains_value_node(item.value, node_type) for item in node.fields)
        case _:
            return False


@dataclass(frozen=True)
class ReachedPathResolver:
    """Reconstruct, from a query's node tree, the relationship chains reaching each related kind.

    A kind maps to every relationship chain that reaches it; a kind reached as a generic peer, or
    through a fragment on a generic, is resolved to the generic's concrete implementations, since a
    data change reports the concrete kind. An inline or named fragment restricts the type of the node it
    sits on rather than reaching another node, so it adds no hop. A kind also read at a root keeps an
    empty chain besides its relationship chains, which maps a changed node to itself. A kind is absent
    -- so a change there widens -- when a way it is reached cannot be pinned: a hop whose field is not a
    relationship with an identifier on an owner that stands for an Infrahub object.

    Each hop carries the filters of the relationship read it stands for, unless a query selects peers through a
    field of a related node or a hierarchy read; then no hop carries any filter.
    """

    queries: list[GraphQLQueryNode]

    @cached_property
    def _records_peer_filters(self) -> bool:
        """Whether no node of the queries selects peers through a field of a related node or a hierarchy read."""
        return not any(_reads_peers_another_way(node) for query in self.queries for node in _iter_nodes(query))

    def _peer_filters(self, node: GraphQLQueryNode) -> PeerFilters | None:
        """The peer filters of a relationship read, or None when the queries record no filter."""
        return _peer_filters(node) if self._records_peer_filters else None

    def resolve(self) -> dict[str, tuple[ReachedPath, ...]]:
        root_kinds = {
            query_model.model.kind for query in self.queries for query_model in query.get_models() if query_model.root
        }
        chains_by_kind: dict[str, set[ReachedPath]] = defaultdict(set)
        ambiguous_kinds: set[str] = set()
        for query in self.queries:
            for node in self._iter_object_nodes(query):
                if node.at_root or node.infrahub_model is None:
                    continue
                chain = self._hop_chain_to_root(node)
                for kind in self._reached_kinds(node):
                    if chain is None:
                        ambiguous_kinds.add(kind)
                    else:
                        chains_by_kind[kind].add(chain)

        for kind in root_kinds & chains_by_kind.keys():
            chains_by_kind[kind].add(ReachedPath(hops=()))
        return {
            kind: tuple(sorted(chains, key=_reached_path_sort_key))
            for kind, chains in chains_by_kind.items()
            if kind not in ambiguous_kinds
        }

    def _reached_kinds(self, node: GraphQLQueryNode) -> list[str]:
        """The concrete kinds a related node stands for: a generic's implementations, else its own."""
        model = node.infrahub_model
        if model is None:
            return []
        if isinstance(model, GenericSchema):
            if node.is_fragment:
                return list(model.concrete_kinds)
            return [implementation.kind for implementation in node.infrahub_node_models]
        return [model.kind]

    def _iter_object_nodes(self, node: GraphQLQueryNode) -> Iterator[GraphQLQueryNode]:
        """Yield every node in the subtree that stands for an Infrahub object."""
        if node.infrahub_model is not None:
            yield node
        for child in node.children:
            yield from self._iter_object_nodes(child)

    def _hop_chain_to_root(self, node: GraphQLQueryNode) -> ReachedPath | None:
        """The chain of reverse relationship hops from a related node back to the query root, or None when a hop cannot be pinned.

        A fragment stands for the node it sits on, so the walk steps over it without a hop. Returns
        None when a hop's field is not a relationship on its owner, or when a fragment sits under the
        metadata of a field rather than on a node, as neither resolves a changed node to a reverse
        relationship.
        """
        hops: list[RelationshipHop] = []
        current = node
        while not current.at_root:
            owner = self._nearest_object_ancestor(current)
            if owner is None or owner.infrahub_model is None:
                return None
            if current.is_fragment:
                if current.parent is None or not current.parent.in_property_level:
                    return None
                current = owner
                continue
            relationship = owner.infrahub_model.get_relationship_or_none(name=current.path)
            if relationship is None or not relationship.identifier:
                return None
            hops.append(
                RelationshipHop(
                    node_kind=owner.infrahub_model.kind,
                    relationship_identifier=relationship.identifier,
                    relationship_direction=relationship.direction,
                    peer_filters=self._peer_filters(current),
                )
            )
            current = owner

        return ReachedPath(hops=tuple(hops))

    def relationship_reads(self) -> tuple[RelationshipRead, ...]:
        """Every relationship the queries read, with its peer filters, once per owner kind.

        A read on a generic owner is recorded once per implementation, as a diff reports the concrete kind.
        """
        reads: set[RelationshipRead] = set()
        for query in self.queries:
            for node in self._iter_object_nodes(query):
                if node.at_root or node.is_fragment or node.infrahub_model is None:
                    continue
                owner = self._nearest_object_ancestor(node)
                if owner is None or owner.infrahub_model is None:
                    continue
                relationship = owner.infrahub_model.get_relationship_or_none(name=node.path)
                if relationship is None or not relationship.identifier:
                    continue
                reads.update(
                    RelationshipRead(
                        owner_kind=owner_kind,
                        relationship_name=relationship.name,
                        relationship_identifier=relationship.identifier,
                        relationship_direction=relationship.direction,
                        peer_kinds=frozenset(self._reached_kinds(node)),
                        peer_filters=self._peer_filters(node),
                    )
                    for owner_kind in owner.infrahub_model.concrete_kinds
                )
        return tuple(sorted(reads, key=lambda read: (read.owner_kind, read.relationship_name, repr(read.peer_filters))))

    def _nearest_object_ancestor(self, node: GraphQLQueryNode) -> GraphQLQueryNode | None:
        """The closest ancestor that stands for an Infrahub object, skipping structural nodes."""
        parent = node.parent
        while parent is not None:
            if parent.infrahub_model is not None:
                return parent
            parent = parent.parent
        return None


@dataclass
class GraphQLQueryReport:
    queries: list[GraphQLQueryNode]
    schema_branch: SchemaBranch | None = None

    @property
    def impacted_models(self) -> list[str]:
        """Return a list of all Infrahub objects that are impacted by queries within the request."""
        models: set[str] = set()
        for query in self.queries:
            query_models = query.get_models()
            models.update([query_model.model.kind for query_model in query_models])

        return sorted(models)

    @cached_property
    def requested_read(self) -> dict[str, ObjectAccess]:
        """Return Infrahub objects and the fields (attributes and relationships) that this query would attempt to read."""
        access: dict[str, ObjectAccess] = {}
        for query in self.queries:
            query_models = query.get_models()
            for query_model in query_models:
                if query_model.model.kind not in access:
                    access[query_model.model.kind] = ObjectAccess()
                access[query_model.model.kind].attributes.update(query_model.attributes)
                access[query_model.model.kind].relationships.update(query_model.relationships)

        return access

    @cached_property
    def filtered_fields_by_kind(self) -> dict[str, set[str]]:
        """Return, per kind, the fields the query's filter arguments select on.

        A filter argument is named after the field it applies to, followed by ``__`` and the filtered
        property (``name__value``, ``owner__name__value``, ``display_label__value``). ``any__value``
        matches every attribute of the kind and ``hfid`` selects on ``human_friendly_id``. Other
        arguments, such as ``ids`` or pagination, select on no field and are left out.
        """
        filtered: dict[str, set[str]] = {}
        for query in self.queries:
            for query_model in query.get_models():
                attribute_names = set(query_model.model.attribute_names)
                field_names = attribute_names | set(query_model.model.relationship_names) | {"display_label"}
                for argument in query_model.arguments:
                    field_name, separator, _ = argument.name.partition("__")
                    if argument.name == "hfid":
                        selected = {"human_friendly_id"}
                    elif not separator:
                        continue
                    elif field_name == "any":
                        selected = attribute_names
                    elif field_name in field_names:
                        selected = {field_name}
                    else:
                        continue
                    filtered.setdefault(query_model.model.kind, set()).update(selected)

        return filtered

    @cached_property
    def traversed_kinds(self) -> set[str]:
        """Return the kinds this query reaches by following a relationship.

        A kind is reported here even when a root query also resolves to it. Both read paths share
        one entry in the requested-read map, so a caller given a changed node of that kind cannot
        tell which path saw it, so the kind is reported as traversed and its reached chains cover both
        reads.

        The concrete kinds standing behind a generic or interface peer are included, because a data
        change is reported against the concrete kind.
        """
        kinds: set[str] = set()
        for query in self.queries:
            for query_model in query.get_models():
                if not query_model.root:
                    kinds.add(query_model.model.kind)

        return kinds

    @cached_property
    def relationship_reached_paths_by_kind(self) -> dict[str, tuple[ReachedPath, ...]]:
        """The relationship chains reaching each related kind that can be narrowed to its owning roots."""
        return ReachedPathResolver(queries=self.queries).resolve()

    @cached_property
    def relationship_reads(self) -> tuple[RelationshipRead, ...]:
        """Every relationship the query reads, with the filters it applies to the peers."""
        return ReachedPathResolver(queries=self.queries).relationship_reads()

    def fields_by_kind(self, kind: str) -> list[str]:
        fields: list[str] = []
        if access := self.requested_read.get(kind):
            fields.extend(list(access.attributes))
            fields.extend(list(access.relationships))

        return fields

    @cached_property
    def variables(self) -> list[GraphQLVariable]:
        """Return input variables defined on the query document.

        All subqueries will use the same document level queries,
        so only the first entry is required
        """
        if self.queries:
            return self.queries[0].variables
        return []

    def _argument_provides_single_value(self, argument: GraphQLArgument, *, allow_required_list: bool = False) -> bool:
        """Indicate whether a filter argument is guaranteed to resolve to exactly one value.

        A list literal (``[$id]``, ``["x"]``) provides a single value only when it holds exactly
        one element that is certain to be provided. A scalar filter provides a single value when
        it is a static literal or a required variable.

        ``allow_required_list`` controls how a required *list-typed* variable is treated. The
        artifact target selector (``ids`` / ``hfid``) is driven per target member, so a required
        list variable there resolves to a single object and is accepted. When pinning the
        components of a uniqueness constraint there is no such guarantee, so a required list
        variable is rejected (it could carry several values and match several objects).
        """
        if argument.kind == "list_value":
            if not isinstance(argument.value, list) or len(argument.value) != 1:
                return False
            element = argument.value[0]
            if isinstance(element, str) and element.startswith("$"):
                variable_name = element.removeprefix("$")
                return any(variable.name == variable_name and variable.required for variable in self.variables)
            # A single statically-defined element is always provided.
            return element is not None

        if not argument.is_variable:
            # A statically-defined value is always provided.
            return True
        return any(
            variable.name == argument.as_variable_name
            and variable.required
            and (allow_required_list or not variable.is_list)
            for variable in self.variables
        )

    @cached_property
    def top_level_kinds(self) -> list[str]:
        return [query.infrahub_model.kind for query in self.queries if query.infrahub_model]

    @cached_property
    def kind_action_map(self) -> dict[str, set[MutateAction]]:
        access: dict[str, set[MutateAction]] = {}
        root_models: set[str] = set()
        includes_mutations: bool = False
        for query in self.queries:
            query_models = query.get_models()
            for query_model in query_models:
                if query_model.mutate_actions:
                    includes_mutations = True
                if includes_mutations:
                    if query_model.model.kind not in access:
                        access[query_model.model.kind] = set()
                    if query_model.root:
                        root_models.add(query_model.model.kind)
                    access[query_model.model.kind].update(query_model.mutate_actions)

        # Until we properly analyze the data payload it is assumed that the required permissions on non-root objects is update
        # the idea around this is that at this point even if we only return data from a relationship without actually updating
        # that relationship we'd still expect to have UPDATE permissions on that related object. However, this is still a step
        # in the right direction as we'd previously require the same permissions as that of the base object so this is still
        # more correct.
        for node_kind, node_actions in access.items():
            if node_kind not in root_models:
                node_actions.add(MutateAction.UPDATE)

        return access

    @property
    def only_has_unique_targets(self) -> bool:
        """Indicate if the query document is defined so that every root query returns a single object."""
        return all(self._query_targets_single_object(query=query) for query in self.queries)

    def _query_targets_single_object(self, query: GraphQLQueryNode) -> bool:
        """Indicate whether a single root query is guaranteed to resolve to one object.

        A query pins a single object when it filters by a required, single ``ids`` or ``hfid``
        value, or when at least one of the node's uniqueness constraints has every one of its
        components pinned by a required, single-valued filter argument.
        """
        model = query.infrahub_model
        if model is None:
            return False

        arguments_by_name = {argument.name: argument for argument in query.arguments}

        for special_filter in ("ids", "hfid"):
            argument = arguments_by_name.get(special_filter)
            if argument is not None and self._argument_provides_single_value(argument, allow_required_list=True):
                return True

        if self.schema_branch is None:
            return False

        try:
            constraint_groups = model.get_unique_constraint_schema_attribute_paths(schema_branch=self.schema_branch)
        except AttributePathParsingError:
            return False

        return any(
            self._constraint_group_is_pinned(group.attributes_paths, arguments_by_name=arguments_by_name)
            for group in constraint_groups
        )

    def _constraint_group_is_pinned(
        self, attribute_paths: list[SchemaAttributePath], arguments_by_name: dict[str, GraphQLArgument]
    ) -> bool:
        """Indicate whether every component of one uniqueness constraint is pinned to a single value."""
        return bool(attribute_paths) and all(
            self._component_is_pinned(attribute_path=attribute_path, arguments_by_name=arguments_by_name)
            for attribute_path in attribute_paths
        )

    def _component_is_pinned(
        self, attribute_path: SchemaAttributePath, arguments_by_name: dict[str, GraphQLArgument]
    ) -> bool:
        """Indicate whether a single uniqueness-constraint component is pinned by a filter argument."""
        relationship_schema = attribute_path.relationship_schema
        if relationship_schema is not None:
            # A relationship can only pin a single target when it points to a single peer.
            if relationship_schema.cardinality != RelationshipCardinality.ONE:
                return False
            # Pin the related peer by a single id or hfid.
            for suffix in ("ids", "hfid"):
                argument = arguments_by_name.get(f"{relationship_schema.name}__{suffix}")
                if argument is not None and self._argument_provides_single_value(argument):
                    return True
            return False

        if attribute_path.attribute_schema is not None:
            property_name = attribute_path.attribute_property_name or "value"
            argument = arguments_by_name.get(f"{attribute_path.attribute_schema.name}__{property_name}")
            return argument is not None and self._argument_provides_single_value(argument)

        return False


class InfrahubGraphQLQueryAnalyzer(GraphQLQueryAnalyzer):
    def __init__(
        self,
        query: str,
        branch: Branch,
        schema_branch: SchemaBranch,
        schema: GraphQLSchema | None = None,
        query_variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
        document: DocumentNode | None = None,
    ) -> None:
        self.branch = branch
        self.schema_branch = schema_branch
        self.operation_name = operation_name
        self.query_variables: dict[str, Any] = query_variables or {}
        self._named_fragments: dict[str, GraphQLQueryNode] = {}
        self._fragment_dependencies: dict[str, set[str]] = {}
        super().__init__(query=query, schema=schema, document=document)

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
        """List of Infrahub models that are referenced in the query.

        Raises:
            ValueError: When the schema has not been provided to the analyzer.

        """
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

        return GraphQLQueryReport(queries=operations, schema_branch=self.schema_branch)

    def _get_operations(self) -> list[GraphQLQueryNode]:
        operations: list[GraphQLQueryNode] = []
        for operation_definition in self._operation_definitions:
            selections = self._get_selections(selection_set=operation_definition.selection_set)

            for field_node in selections.field_nodes:
                schema_model: MainSchemaTypes
                infrahub_node_models: list[MainSchemaTypes] = []
                model_name = self._get_model_name(node=field_node, operation_definition=operation_definition)

                if model_name in self.schema_branch.node_names:
                    schema_model = self.schema_branch.get_node(name=model_name, duplicate=False)
                elif model_name in self.schema_branch.generic_names:
                    schema_model = self.schema_branch.get_generic(name=model_name, duplicate=False)
                    infrahub_node_models = [
                        self.schema_branch.get(name=used_by, duplicate=False) for used_by in schema_model.used_by
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
                    mutate_actions=self._get_model_mutations(
                        node=field_node, operation_definition=operation_definition
                    ),
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
        if operation_definition.operation == OperationType.MUTATION and node.name.value.endswith(
            ("Create", "Delete", "Update", "Upsert")
        ):
            return node.name.value[:-6]
        return node.name.value

    @staticmethod
    def _get_model_mutations(node: FieldNode, operation_definition: OperationDefinitionNode) -> list[MutateAction]:
        if operation_definition.operation == OperationType.MUTATION:
            if node.name.value.endswith("Create"):
                return [MutateAction.CREATE]
            if node.name.value.endswith("Delete"):
                return [MutateAction.DELETE]
            if node.name.value.endswith("Update"):
                return [MutateAction.UPDATE]
            if node.name.value.endswith("Upsert"):
                return [MutateAction.CREATE, MutateAction.UPDATE]
        return []

    @property
    def _sorted_fragment_definitions(self) -> list[FragmentDefinitionNode]:
        """Sort fragments so that we start processing fragments that don't depend on other fragments.

        Raises:
            ValueError: When a circular dependency is detected between fragments.

        """
        dependencies = deepcopy(self._fragment_dependencies)

        independent_fragments = deque([frag for frag, deps in dependencies.items() if not deps])

        sorted_fragments = []

        while independent_fragments:
            fragment_name = independent_fragments.popleft()
            sorted_fragments.append(fragment_name)

            for dependent, deps in dependencies.items():
                if fragment_name in deps:
                    deps.remove(fragment_name)
                    if not deps:
                        independent_fragments.append(dependent)

        if len(sorted_fragments) != len(self._fragment_dependencies):
            raise ValueError("Circular fragment dependency detected.")

        fragment_name_to_definition = {frag.name.value: frag for frag in self._fragment_definitions}
        return [fragment_name_to_definition[name] for name in sorted_fragments]

    def _populate_fragment_dependency(self, name: str, selection_set: SelectionSetNode | None) -> None:
        if selection_set:
            for selection in selection_set.selections:
                if isinstance(selection, FragmentSpreadNode):
                    self._fragment_dependencies[name].add(selection.name.value)
                elif isinstance(selection, FieldNode):
                    self._populate_fragment_dependency(name=name, selection_set=selection.selection_set)
                elif isinstance(selection, InlineFragmentNode):
                    self._populate_fragment_dependency(name=name, selection_set=selection.selection_set)

    def _populate_fragment_dependencies(self) -> None:
        for fragment in self._fragment_definitions:
            fragment_name = fragment.name.value
            self._fragment_dependencies[fragment_name] = set()
            self._populate_fragment_dependency(name=fragment_name, selection_set=fragment.selection_set)

    def _populate_named_fragments(self) -> None:
        self._populate_fragment_dependencies()
        self._named_fragments = {}

        for fragment_definition in self._sorted_fragment_definitions:
            fragment_name = fragment_definition.name.value
            condition_name = fragment_definition.type_condition.name.value
            selections = self._get_selections(selection_set=fragment_definition.selection_set)

            try:
                infrahub_model = self.schema_branch.get(name=condition_name, duplicate=False)
            except SchemaNotFoundError:
                infrahub_model = None

            named_fragment = GraphQLQueryNode(
                path=fragment_definition.type_condition.name.value,
                context_type=ContextType.DIRECT,
                infrahub_model=infrahub_model,
                is_fragment=True,
            )
            self._populate_children(selections=selections, query_node=named_fragment)

            self._named_fragments[fragment_name] = named_fragment

    def _populate_field_node(self, node: FieldNode, query_node: GraphQLQueryNode) -> GraphQLQueryNode:
        context_type = query_node.context_type
        infrahub_model = None
        infrahub_node_models: list[MainSchemaTypes] = []
        if query_node.in_property_level:
            if model := query_node.context_model():
                if node.name.value in model.attribute_names:
                    query_node.append_attribute(attribute=node.name.value)
                elif node_property := NODE_PROPERTY_BY_QUERY_FIELD.get(node.name.value):
                    query_node.append_attribute(attribute=node_property)
                elif node.name.value in model.relationship_names:
                    rel = model.get_relationship_or_none(name=node.name.value)
                    if rel:
                        infrahub_model = self.schema_branch.get(name=rel.peer, duplicate=False)
                        if isinstance(infrahub_model, GenericSchema):
                            infrahub_node_models = [
                                self.schema_branch.get(name=used_by, duplicate=False)
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
            self._populate_children(
                selections=self._get_selections(selection_set=node.selection_set), query_node=current_node
            )

        return current_node

    def _populate_children(self, selections: GraphQLSelectionSet, query_node: GraphQLQueryNode) -> None:
        """Add a child node for every field, inline fragment and fragment spread of a selection set."""
        for field_node in selections.field_nodes:
            query_node.children.append(self._populate_field_node(node=field_node, query_node=query_node))
        for inline_fragment_node in selections.inline_fragment_nodes:
            query_node.children.append(
                self._populate_inline_fragment_node(node=inline_fragment_node, query_node=query_node)
            )
        for fragment_spread_node in selections.fragment_spread_nodes:
            if fragment_spread_node.name.value not in self._named_fragments:
                continue
            query_node.children.append(
                self._populate_fragment_spread_node(node=fragment_spread_node, query_node=query_node)
            )

    def _populate_inline_fragment_node(
        self, node: InlineFragmentNode, query_node: GraphQLQueryNode
    ) -> GraphQLQueryNode:
        context_type = query_node.context_type
        infrahub_model = self.schema_branch.get(name=node.type_condition.name.value, duplicate=False)
        context_type = ContextType.DIRECT
        current_node = GraphQLQueryNode(
            parent=query_node,
            path=node.type_condition.name.value,
            context_type=context_type,
            infrahub_model=infrahub_model,
            is_fragment=True,
        )
        if node.selection_set:
            self._populate_children(
                selections=self._get_selections(selection_set=node.selection_set), query_node=current_node
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

    def _get_variables(self, operation: OperationDefinitionNode) -> list[GraphQLVariable]:
        variables: list[GraphQLVariable] = []

        for variable in operation.variable_definitions or []:
            type_node: TypeNode = variable.type
            required = False
            is_list = False
            inner_required = False

            if isinstance(type_node, NonNullTypeNode):
                required = True
                type_node = type_node.type

            if isinstance(type_node, ListTypeNode):
                is_list = True
                inner_type = type_node.type

                if isinstance(inner_type, NonNullTypeNode):
                    inner_required = True
                    inner_type = inner_type.type

                if isinstance(inner_type, NamedTypeNode):
                    type_name = inner_type.name.value
                else:
                    raise TypeError(f"Unsupported inner type node: {inner_type}")
            elif isinstance(type_node, NamedTypeNode):
                type_name = type_node.name.value
            else:
                raise TypeError(f"Unsupported type node: {type_node}")

            variables.append(
                GraphQLVariable(
                    name=variable.variable.name.value,
                    type=type_name,
                    required=required,
                    is_list=is_list,
                    inner_required=inner_required,
                    default=_parse_value_node(variable.default_value) if variable.default_value else None,
                )
            )

        return variables

    def _parse_arguments(self, field_node: FieldNode) -> list[GraphQLArgument]:
        return [
            GraphQLArgument(name=argument.name.value, value_node=argument.value) for argument in field_node.arguments
        ]


def _parse_value_node(node: ValueNode) -> Any:
    """Return the Python value a query literal stands for, a variable reading as its ``$``-prefixed name.

    Raises:
        TypeError: When the node is not a value the parser can produce.

    """
    match node:
        case VariableNode():
            value: Any = f"${node.name.value}"
        case IntValueNode():
            value = int(node.value)
        case FloatValueNode():
            value = float(node.value)
        case StringValueNode():
            value = node.value
        case BooleanValueNode():
            value = node.value
        case NullValueNode():
            value = None
        case EnumValueNode():
            value = node.value
        case ListValueNode() | ConstListValueNode():
            value = [_parse_value_node(item) for item in node.values]
        case ObjectValueNode() | ConstObjectValueNode():
            value = {field.name.value: _parse_value_node(field.value) for field in node.fields}
        case _:
            raise TypeError(f"Unsupported value node: {node}")

    return value
