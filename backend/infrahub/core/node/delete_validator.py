from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, RelationshipDeleteBehavior
from infrahub.core.node import Node
from infrahub.core.query.relationship import (
    FullRelationshipIdentifier,
    RelationshipGetByIdentifierInWindowsQuery,
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
    dependents: defaultdict[str, list[RelationshipPeersData]] = field(default_factory=lambda: defaultdict(list))
    """The links of each peer that has a required relationship to a node being deleted, keyed by peer id."""
    cascades: defaultdict[str, list[RelationshipPeersData]] = field(default_factory=lambda: defaultdict(list))
    """The cascading links that reach each node, keyed by the id of the node reached."""

    def get_dependents_left_behind(self) -> list[RelationshipPeersData]:
        return [
            peer_data
            for peer_id, peers_data in self.dependents.items()
            if peer_id not in self.node_ids_to_delete
            for peer_data in peers_data
        ]


@dataclass(frozen=True)
class DeleteBlock:
    """A link that keeps a node from being deleted."""

    deleted_kind: str
    deleted_id: str
    identifier: str
    peer_kind: str
    peer_id: str
    relationship_type: DeleteRelationshipType
    """Dependent when the peer has a required relationship to the deleted node, cascade when the peer is left behind
    although the deleted node's relationship would delete it."""

    @property
    def sort_key(self) -> tuple[str, ...]:
        return (
            self.deleted_kind,
            self.deleted_id,
            self.identifier,
            self.peer_kind,
            self.peer_id,
            self.relationship_type.value,
        )

    @classmethod
    def from_peer_data(cls, peer_data: RelationshipPeersData, relationship_type: DeleteRelationshipType) -> Self:
        return cls(
            deleted_kind=peer_data.source_kind,
            deleted_id=str(peer_data.source_id),
            identifier=peer_data.identifier,
            peer_kind=peer_data.destination_kind,
            peer_id=str(peer_data.destination_id),
            relationship_type=relationship_type,
        )


def _format_branch_names(branch_names: Iterable[str]) -> str:
    sorted_names = sorted(branch_names)
    quoted_names = ", ".join(f"'{branch_name}'" for branch_name in sorted_names)
    if len(sorted_names) == 1:
        return f"branch {quoted_names}"
    return f"branches {quoted_names}"


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

    async def _analyze_delete_dependencies(self, start_nodes: Iterable[Node], at: Timestamp) -> set[str]:
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
        raise ValidationError(
            [
                self._build_required_peer_error(
                    block=DeleteBlock.from_peer_data(
                        peer_data=peer_data, relationship_type=DeleteRelationshipType.DEPENDENT_NODE
                    )
                )
                for peer_data in missing_delete_peers_data
            ]
        )

    async def _analyze_delete_dependencies_in_windows(self, start_nodes: Iterable[Node], at: Timestamp) -> set[str]:
        """Check the delete in the window of every live branch, because a branch-agnostic node is deleted on all of them.

        A branch-aware node is deleted on the request branch only, so the request branch's window decides the nodes to
        delete, and every other window loses only the branch-agnostic nodes among them.

        Raises:
            ValidationError: A window keeps a peer with a required relationship to a node deleted in it, or a window
                keeps a node that a cascade from a branch-agnostic node reaches and the request branch's window does not.

        """
        start_kind_by_id = {node.get_id(): node.get_schema().kind for node in start_nodes}
        start_ids = set(start_kind_by_id)
        full_relationship_identifiers = self.index.get_relationship_identifiers()
        if not full_relationship_identifiers:
            return start_ids

        request_window_name = registry.default_branch if self.branch.name == GLOBAL_BRANCH_NAME else self.branch.name
        peer_data_by_window = await self._get_peer_data_by_window(
            start_ids=start_ids,
            full_identifiers=full_relationship_identifiers,
            request_window_name=request_window_name,
            at=at,
        )
        request_walk = self._walk(
            start_ids=start_ids, peer_data_by_source_id=peer_data_by_window.get(request_window_name, {})
        )

        blocking_branch_names: defaultdict[DeleteBlock, set[str]] = defaultdict(set)
        for peer_data in request_walk.get_dependents_left_behind():
            block = DeleteBlock.from_peer_data(
                peer_data=peer_data, relationship_type=DeleteRelationshipType.DEPENDENT_NODE
            )
            blocking_branch_names[block].add(request_window_name)

        agnostic_ids = self._get_branch_agnostic_ids(start_kind_by_id=start_kind_by_id, request_walk=request_walk)
        for window_name, peer_data_by_source_id in peer_data_by_window.items():
            if window_name == request_window_name:
                continue
            for block in self._get_blocks_in_other_window(
                agnostic_ids=agnostic_ids,
                request_ids_to_delete=request_walk.node_ids_to_delete,
                peer_data_by_source_id=peer_data_by_source_id,
            ):
                blocking_branch_names[block].add(window_name)

        if blocking_branch_names:
            raise ValidationError(
                [
                    self._build_window_block_error(block=block, branch_names=blocking_branch_names[block])
                    for block in sorted(blocking_branch_names, key=lambda block: block.sort_key)
                ]
            )
        return request_walk.node_ids_to_delete

    async def _get_peer_data_by_window(
        self,
        start_ids: set[str],
        full_identifiers: list[FullRelationshipIdentifier],
        request_window_name: str,
        at: Timestamp,
    ) -> defaultdict[str, defaultdict[str, list[RelationshipPeersData]]]:
        """Read the links of the start nodes and of every node a cascade reaches in the request branch's window.

        Return the links keyed by window name, then by the id of the node they start from.
        """
        peer_data_by_window: defaultdict[str, defaultdict[str, list[RelationshipPeersData]]] = defaultdict(
            lambda: defaultdict(list)
        )
        queried_ids: set[str] = set()
        ids_to_query = set(start_ids)
        while ids_to_query:
            query = await RelationshipGetByIdentifierInWindowsQuery.init(
                db=self.db,
                full_identifiers=full_identifiers,
                source_ids=sorted(ids_to_query),
                branch=self.branch,
                at=at,
            )
            await query.execute(db=self.db)
            queried_ids |= ids_to_query
            ids_to_query = set()
            for window_peer_data in query.get_peers():
                peer_data = window_peer_data.peer_data
                peer_data_by_window[window_peer_data.window_name][str(peer_data.source_id)].append(peer_data)
                if window_peer_data.window_name == request_window_name and self._is_cascade(peer_data=peer_data):
                    ids_to_query.add(str(peer_data.destination_id))
            ids_to_query -= queried_ids
        return peer_data_by_window

    def _get_branch_agnostic_ids(self, start_kind_by_id: dict[str, str], request_walk: DeleteWalk) -> set[str]:
        kind_by_id = dict(start_kind_by_id)
        for peer_id, peers_data in request_walk.cascades.items():
            kind_by_id[peer_id] = peers_data[0].destination_kind
        return {
            node_id
            for node_id, kind in kind_by_id.items()
            if self._all_schemas_map[kind].branch == BranchSupportType.AGNOSTIC
        }

    def _get_blocks_in_other_window(
        self,
        agnostic_ids: set[str],
        request_ids_to_delete: set[str],
        peer_data_by_source_id: dict[str, list[RelationshipPeersData]],
    ) -> list[DeleteBlock]:
        """Return the links that block the delete in a window other than the request branch's.

        Only the branch-agnostic nodes are deleted in that window, so cascades from branch-aware nodes are not followed.
        """
        blocks: list[DeleteBlock] = []
        for node_id in agnostic_ids:
            for peer_data in peer_data_by_source_id.get(node_id, []):
                relationship_types = self._get_relationship_types(peer_data=peer_data)
                peer_id = str(peer_data.destination_id)
                if DeleteRelationshipType.DEPENDENT_NODE in relationship_types and peer_id not in agnostic_ids:
                    blocks.append(
                        DeleteBlock.from_peer_data(
                            peer_data=peer_data, relationship_type=DeleteRelationshipType.DEPENDENT_NODE
                        )
                    )
                elif (
                    DeleteRelationshipType.CASCADE_DELETE in relationship_types and peer_id not in request_ids_to_delete
                ):
                    blocks.append(
                        DeleteBlock.from_peer_data(
                            peer_data=peer_data, relationship_type=DeleteRelationshipType.CASCADE_DELETE
                        )
                    )
        return blocks

    def _get_relationship_types(self, peer_data: RelationshipPeersData) -> set[DeleteRelationshipType]:
        return self.index.get_relationship_types(
            src_kind=peer_data.source_kind, relationship_identifier=peer_data.identifier
        )

    def _is_cascade(self, peer_data: RelationshipPeersData) -> bool:
        return DeleteRelationshipType.CASCADE_DELETE in self._get_relationship_types(peer_data=peer_data)

    def _walk(self, start_ids: set[str], peer_data_by_source_id: dict[str, list[RelationshipPeersData]]) -> DeleteWalk:
        walk = DeleteWalk()
        node_ids_to_check = set(start_ids)
        while node_ids_to_check:
            node_id = node_ids_to_check.pop()
            walk.node_ids_to_delete.add(node_id)
            for peer_data in peer_data_by_source_id.get(node_id, []):
                relationship_types = self._get_relationship_types(peer_data=peer_data)
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

    def _build_window_block_error(self, block: DeleteBlock, branch_names: set[str]) -> ValidationError:
        if block.relationship_type == DeleteRelationshipType.CASCADE_DELETE:
            return self._build_cascade_error(block=block, branch_names=branch_names)
        return self._build_required_peer_error(block=block, branch_names=branch_names)

    def _build_required_peer_error(self, block: DeleteBlock, branch_names: set[str] | None = None) -> ValidationError:
        peer_rel_name = self._all_schemas_map[block.peer_kind].get_relationship_by_identifier(block.identifier).name
        err_msg = f"Cannot delete {block.deleted_kind} '{block.deleted_id}'."
        err_msg += (
            f" It is linked to mandatory relationship {peer_rel_name} on node {block.peer_kind} '{block.peer_id}'"
        )
        if branch_names:
            err_msg += f" on {_format_branch_names(branch_names)}"
        return ValidationError({f"{block.peer_kind}.{peer_rel_name}": err_msg})

    def _build_cascade_error(self, block: DeleteBlock, branch_names: set[str]) -> ValidationError:
        rel_name = self._all_schemas_map[block.deleted_kind].get_relationship_by_identifier(block.identifier).name
        err_msg = (
            f"Cannot delete {block.deleted_kind} '{block.deleted_id}'. Deleting it would also delete"
            f" {block.peer_kind} '{block.peer_id}' through relationship {rel_name} on"
            f" {_format_branch_names(branch_names)}, but this delete does not remove that node there"
        )
        return ValidationError({f"{block.deleted_kind}.{rel_name}": err_msg})
