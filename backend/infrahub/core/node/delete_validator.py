from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, RelationshipDeleteBehavior
from infrahub.core.node import Node
from infrahub.core.query.relationship import (
    FullRelationshipIdentifier,
    RelationshipGetByIdentifierQuery,
    RelationshipPeersData,
)
from infrahub.core.schema import MainSchemaTypes, NodeSchema, ProfileSchema, TemplateSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


class DeleteRelationshipType(Enum):
    CASCADE_DELETE = "cascade"
    DEPENDENT_NODE = "dependent"


@dataclass
class DeleteWalk:
    """What deleting the start nodes reaches through one set of links."""

    node_ids_to_delete: set[str] = field(default_factory=set)
    dependents: dict[str, list[RelationshipPeersData]] = field(default_factory=lambda: defaultdict(list))
    """The links of each peer that has a required relationship to a node being deleted, keyed by peer id."""
    cascades: dict[str, list[RelationshipPeersData]] = field(default_factory=lambda: defaultdict(list))
    """The cascading links that reach each node, keyed by the id of the node reached."""

    def get_dependents_left_behind(self) -> list[RelationshipPeersData]:
        return [
            peer_data
            for peer_id, peers_data in self.dependents.items()
            if peer_id not in self.node_ids_to_delete
            for peer_data in peers_data
        ]

    def get_cascades_outside(self, node_ids: set[str]) -> list[RelationshipPeersData]:
        """Return the cascading links that reach a node outside `node_ids`."""
        return [
            peer_data
            for peer_id, peers_data in self.cascades.items()
            if peer_id not in node_ids
            for peer_data in peers_data
        ]


class NodeDeleteIndex:
    def __init__(self, all_schemas_map: dict[str, MainSchemaTypes]) -> None:
        self._all_schemas_map = all_schemas_map
        # {node_schema: {DeleteRelationshipType: {relationship_identifier: peer_node_schema}}}
        self._dependency_graph: dict[str, dict[DeleteRelationshipType, dict[str, set[str]]]] = {}

    def index(self, start_schemas: Iterable[NodeSchema | ProfileSchema | TemplateSchema]) -> None:
        cascade_kinds = self._index_cascading_deletes(start_schemas=start_schemas)
        self._index_dependent_schema(cascade_kinds=cascade_kinds)

    def _get_schema_kinds(self, schema_kind: str) -> set[str]:
        schema = self._all_schemas_map[schema_kind]
        if schema.is_node_schema:
            return {schema_kind}
        used_by = getattr(schema, "used_by", None)
        if schema.is_generic_schema and used_by:
            return set(used_by)
        return set()

    def _add_to_dependency_graph(
        self, kind: str, relationship_type: DeleteRelationshipType, relationship_identifier: str, peer_kinds: set[str]
    ) -> None:
        if kind not in self._dependency_graph:
            self._dependency_graph[kind] = {}
        if relationship_type not in self._dependency_graph[kind]:
            self._dependency_graph[kind][relationship_type] = defaultdict(set)
        self._dependency_graph[kind][relationship_type][relationship_identifier].update(peer_kinds)

    def _index_cascading_deletes(
        self, start_schemas: Iterable[NodeSchema | ProfileSchema | TemplateSchema]
    ) -> set[str]:
        visited: set[str] = set()
        kinds_to_check: set[str] = {schema.kind for schema in start_schemas}
        while True:
            try:
                kind_to_check = kinds_to_check.pop()
            except KeyError:
                break
            visited.add(kind_to_check)
            node_schema = self._all_schemas_map[kind_to_check]
            for relationship_schema in node_schema.relationships:
                if relationship_schema.on_delete != RelationshipDeleteBehavior.CASCADE:
                    continue
                peer_kinds = self._get_schema_kinds(schema_kind=relationship_schema.peer)
                self._add_to_dependency_graph(
                    kind=kind_to_check,
                    relationship_type=DeleteRelationshipType.CASCADE_DELETE,
                    relationship_identifier=relationship_schema.get_identifier(),
                    peer_kinds=peer_kinds,
                )
                for peer_kind in peer_kinds:
                    if peer_kind not in visited:
                        kinds_to_check.add(peer_kind)
        return visited

    def _index_dependent_schema(self, cascade_kinds: set[str]) -> None:
        start_schema_kinds: set[str] = set()
        for kind in cascade_kinds:
            start_schema_kinds.add(kind)
            schema = self._all_schemas_map[kind]
            if isinstance(schema, (NodeSchema, ProfileSchema, TemplateSchema)):
                start_schema_kinds.update(schema.inherit_from)
        for node_schema in self._all_schemas_map.values():
            for relationship_schema in node_schema.relationships:
                if relationship_schema.optional is True or relationship_schema.peer not in start_schema_kinds:
                    continue

                for peer_kind in self._get_schema_kinds(schema_kind=relationship_schema.peer):
                    self._add_to_dependency_graph(
                        kind=peer_kind,
                        relationship_type=DeleteRelationshipType.DEPENDENT_NODE,
                        relationship_identifier=relationship_schema.get_identifier(),
                        peer_kinds={node_schema.kind},
                    )

    def get_relationship_identifiers(self) -> list[FullRelationshipIdentifier]:
        full_relationship_identifiers = []
        for node_kind, relationship_type_details in self._dependency_graph.items():
            for relationship_map in relationship_type_details.values():
                for relationship_identifier, peer_kinds in relationship_map.items():
                    full_relationship_identifiers.extend(
                        [
                            FullRelationshipIdentifier(
                                source_kind=node_kind, identifier=relationship_identifier, destination_kind=peer_kind
                            )
                            for peer_kind in peer_kinds
                        ]
                    )
        return full_relationship_identifiers

    def get_relationship_types(self, src_kind: str, relationship_identifier: str) -> set[DeleteRelationshipType]:
        relationship_types: set[DeleteRelationshipType] = set()
        if src_kind not in self._dependency_graph:
            return relationship_types
        for relationship_type, relationships_map in self._dependency_graph[src_kind].items():
            if relationship_identifier in relationships_map:
                relationship_types.add(relationship_type)
        return relationship_types


class NodeDeleteValidator:
    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch
        schema_branch = registry.schema.get_schema_branch(name=self.branch.name)
        self._all_schemas_map = schema_branch.get_all(duplicate=False)
        self.index: NodeDeleteIndex = NodeDeleteIndex(all_schemas_map=self._all_schemas_map)

    async def get_ids_to_delete(self, nodes: Iterable[Node], at: Timestamp | str | None = None) -> set[str]:
        start_schemas = {node.get_schema() for node in nodes}
        self.index.index(start_schemas=start_schemas)
        at = Timestamp(at)

        if any(schema.branch == BranchSupportType.AGNOSTIC for schema in start_schemas):
            return await self._analyze_delete_dependencies_in_windows(start_nodes=nodes, at=at)
        return await self._analyze_delete_dependencies(start_nodes=nodes, at=at)

    async def _analyze_delete_dependencies(self, start_nodes: Iterable[Node], at: Timestamp | str | None) -> set[str]:
        full_relationship_identifiers = self.index.get_relationship_identifiers()
        if not full_relationship_identifiers:
            return {node.get_id() for node in start_nodes}

        query = await RelationshipGetByIdentifierQuery.init(
            db=self.db, full_identifiers=full_relationship_identifiers, branch=self.branch, at=at
        )
        await query.execute(db=self.db)

        peer_data_by_source_id = self._build_peer_data_map(peers_datas=query.get_peers())
        walk = self._walk(
            start_ids={node.get_id() for node in start_nodes}, peer_data_by_source_id=peer_data_by_source_id
        )

        missing_delete_peers_data = walk.get_dependents_left_behind()
        if not missing_delete_peers_data:
            return walk.node_ids_to_delete
        raise self._build_validation_error(missing_delete_peers_data=missing_delete_peers_data)

    async def _analyze_delete_dependencies_in_windows(self, start_nodes: Iterable[Node], at: Timestamp) -> set[str]:
        """Walk the delete in the window of every live branch, because a branch-agnostic node is deleted on all of them.

        The nodes to delete are those reached in the request branch's window. Raise when, in any window, a required
        peer is left behind or a cascade reaches a node that the request branch's window does not reach.

        Raises:
            ValidationError: A window holds a required peer left behind, or a cascade outside the request branch's window.

        """
        start_ids = {node.get_id() for node in start_nodes}
        full_relationship_identifiers = self.index.get_relationship_identifiers()
        if not full_relationship_identifiers:
            return start_ids

        peer_data_by_window = await self._get_peer_data_by_window(
            start_ids=start_ids, full_identifiers=full_relationship_identifiers, at=at
        )
        request_window_name = registry.default_branch if self.branch.name == GLOBAL_BRANCH_NAME else self.branch.name
        request_walk = self._walk(
            start_ids=start_ids, peer_data_by_source_id=peer_data_by_window.get(request_window_name, {})
        )

        validation_errors: list[ValidationError] = []
        for window_name in sorted(peer_data_by_window):
            walk = (
                request_walk
                if window_name == request_window_name
                else self._walk(start_ids=start_ids, peer_data_by_source_id=peer_data_by_window[window_name])
            )
            blocking_peers_data = walk.get_dependents_left_behind() + walk.get_cascades_outside(
                node_ids=request_walk.node_ids_to_delete
            )
            if blocking_peers_data:
                validation_errors.append(
                    self._build_validation_error(missing_delete_peers_data=blocking_peers_data, branch_name=window_name)
                )

        if validation_errors:
            raise ValidationError(validation_errors)
        return request_walk.node_ids_to_delete

    async def _get_peer_data_by_window(
        self, start_ids: set[str], full_identifiers: list[FullRelationshipIdentifier], at: Timestamp
    ) -> dict[str, dict[str, list[RelationshipPeersData]]]:
        """Read the links of the start nodes and of every node a cascade reaches in any window, one level at a time.

        Return the links keyed by window name, then by the id of the node they start from.

        Raises:
            ValueError: A link was read without the name of its window.

        """
        peer_data_by_window: dict[str, dict[str, list[RelationshipPeersData]]] = defaultdict(lambda: defaultdict(list))
        queried_ids: set[str] = set()
        ids_to_query = set(start_ids)
        while ids_to_query:
            query = await RelationshipGetByIdentifierQuery.init(
                db=self.db,
                full_identifiers=full_identifiers,
                window_source_ids=sorted(ids_to_query),
                branch=self.branch,
                at=at,
            )
            await query.execute(db=self.db)
            queried_ids |= ids_to_query
            ids_to_query = set()
            for peer_data in query.get_peers():
                if peer_data.window_name is None:
                    raise ValueError(f"The link {peer_data.id} was read without the name of its branch window")
                peer_data_by_window[peer_data.window_name][str(peer_data.source_id)].append(peer_data)
                relationship_types = self.index.get_relationship_types(
                    src_kind=peer_data.source_kind, relationship_identifier=peer_data.identifier
                )
                if DeleteRelationshipType.CASCADE_DELETE in relationship_types:
                    ids_to_query.add(str(peer_data.destination_id))
            ids_to_query -= queried_ids
        return peer_data_by_window

    def _walk(self, start_ids: set[str], peer_data_by_source_id: dict[str, list[RelationshipPeersData]]) -> DeleteWalk:
        walk = DeleteWalk()
        node_ids_to_check = set(start_ids)
        while node_ids_to_check:
            node_id = node_ids_to_check.pop()
            walk.node_ids_to_delete.add(node_id)
            for peer_data in peer_data_by_source_id.get(node_id, []):
                relationship_types = self.index.get_relationship_types(
                    src_kind=peer_data.source_kind, relationship_identifier=peer_data.identifier
                )
                peer_id = str(peer_data.destination_id)
                if DeleteRelationshipType.CASCADE_DELETE in relationship_types:
                    walk.cascades[peer_id].append(peer_data)
                    if peer_id not in walk.node_ids_to_delete:
                        node_ids_to_check.add(peer_id)
                if DeleteRelationshipType.DEPENDENT_NODE in relationship_types:
                    walk.dependents[peer_id].append(peer_data)
        return walk

    def _build_peer_data_map(
        self, peers_datas: Iterable[RelationshipPeersData]
    ) -> dict[str, list[RelationshipPeersData]]:
        peer_data_by_source_id: dict[str, list[RelationshipPeersData]] = {}
        for peer_data in peers_datas:
            source_id = str(peer_data.source_id)
            if source_id not in peer_data_by_source_id:
                peer_data_by_source_id[source_id] = []
            peer_data_by_source_id[source_id].append(peer_data)
            # check if this relationship also needs to be tracked going the other way
            if not self.index.get_relationship_types(
                src_kind=peer_data.destination_kind, relationship_identifier=peer_data.identifier
            ):
                continue
            dest_id = str(peer_data.destination_id)
            if dest_id not in peer_data_by_source_id:
                peer_data_by_source_id[dest_id] = []
            peer_data_by_source_id[dest_id].append(peer_data.reversed())
        return peer_data_by_source_id

    def _build_validation_error(
        self, missing_delete_peers_data: Iterable[RelationshipPeersData], branch_name: str | None = None
    ) -> ValidationError:
        validation_errors = []
        for peers_data in missing_delete_peers_data:
            peer_kind = peers_data.destination_kind
            peer_schema = self._all_schemas_map[peer_kind]
            peer_rel = peer_schema.get_relationship_by_identifier(peers_data.identifier, raise_on_error=False)
            if peer_rel is None:
                # A cascading relationship can be declared on the deleted side only.
                source_schema = self._all_schemas_map[peers_data.source_kind]
                peer_rel = source_schema.get_relationship_by_identifier(peers_data.identifier)
            peer_rel_name = peer_rel.name
            peer_path = f"{peer_kind}.{peer_rel_name}"
            err_msg = f"Cannot delete {peers_data.source_kind} '{peers_data.source_id}'."
            err_msg += f" It is linked to mandatory relationship {peer_rel_name} on node {peer_kind} '{peers_data.destination_id}'"
            if branch_name is not None:
                err_msg += f" on branch '{branch_name}'"
            validation_errors.append(ValidationError({peer_path: err_msg}))

        return ValidationError(validation_errors)
