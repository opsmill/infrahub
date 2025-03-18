from collections import defaultdict
from enum import Enum
from typing import Iterable

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipDeleteBehavior
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


class NodeDeleteIndex:
    def __init__(self, all_schemas_map: dict[str, MainSchemaTypes]) -> None:
        self._all_schemas_map = all_schemas_map
        # {node_schema: {DeleteRelationshipType: {relationship_identifier: peer_node_schema}}}
        self._dependency_graph: dict[str, dict[DeleteRelationshipType, dict[str, set[str]]]] = {}

    def index(self, start_schemas: Iterable[NodeSchema | ProfileSchema | TemplateSchema]) -> None:
        self._index_cascading_deletes(start_schemas=start_schemas)
        self._index_dependent_schema(start_schemas=start_schemas)

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

    def _index_cascading_deletes(self, start_schemas: Iterable[NodeSchema | ProfileSchema | TemplateSchema]) -> None:
        kinds_to_check: set[str] = {schema.kind for schema in start_schemas}
        while True:
            try:
                kind_to_check = kinds_to_check.pop()
            except KeyError:
                break
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
                    if peer_kind not in self._dependency_graph:
                        kinds_to_check.add(peer_kind)

    def _index_dependent_schema(self, start_schemas: Iterable[NodeSchema | ProfileSchema | TemplateSchema]) -> None:
        start_schema_kinds: set[str] = set()
        for start_schema in start_schemas:
            start_schema_kinds.add(start_schema.kind)
            if start_schema.inherit_from:
                start_schema_kinds.update(set(start_schema.inherit_from))
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
    def __init__(self, db: InfrahubDatabase, branch: Branch):
        self.db = db
        self.branch = branch
        schema_branch = registry.schema.get_schema_branch(name=self.branch.name)
        self._all_schemas_map = schema_branch.get_all(duplicate=False)
        self.index: NodeDeleteIndex = NodeDeleteIndex(all_schemas_map=self._all_schemas_map)

    async def get_ids_to_delete(self, nodes: Iterable[Node], at: Timestamp | str | None = None) -> set[str]:
        start_schemas = {node.get_schema() for node in nodes}
        self.index.index(start_schemas=start_schemas)
        at = Timestamp(at)

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
        node_ids_to_check = {node.get_id() for node in start_nodes}
        node_ids_to_delete: set[str] = set()
        dependent_node_details_map: dict[str, list[RelationshipPeersData]] = {}

        while node_ids_to_check:
            node_id = node_ids_to_check.pop()
            node_ids_to_delete.add(node_id)
            if node_id not in peer_data_by_source_id:
                continue
            peer_data_list = peer_data_by_source_id[node_id]
            for peer_data in peer_data_list:
                relationship_types = self.index.get_relationship_types(
                    src_kind=peer_data.source_kind, relationship_identifier=peer_data.identifier
                )
                peer_id = str(peer_data.destination_id)
                if DeleteRelationshipType.CASCADE_DELETE in relationship_types:
                    if peer_id not in node_ids_to_delete:
                        node_ids_to_check.add(peer_id)
                if DeleteRelationshipType.DEPENDENT_NODE in relationship_types:
                    if peer_id not in dependent_node_details_map:
                        dependent_node_details_map[peer_id] = []
                    dependent_node_details_map[peer_id].append(peer_data)

        missing_delete_ids = set(dependent_node_details_map.keys()) - node_ids_to_delete
        if not missing_delete_ids:
            return node_ids_to_delete
        missing_delete_peers_data = []
        for peers_data_list in dependent_node_details_map.values():
            missing_delete_peers_data.extend(peers_data_list)
        validation_error = self._build_validation_error(missing_delete_peers_data=missing_delete_peers_data)
        raise validation_error

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

    def _build_validation_error(self, missing_delete_peers_data: Iterable[RelationshipPeersData]) -> ValidationError:
        validation_errors = []
        for peers_data in missing_delete_peers_data:
            peer_kind = peers_data.destination_kind
            peer_schema = self._all_schemas_map[peer_kind]
            peer_rel_name = peer_schema.get_relationship_by_identifier(peers_data.identifier).name
            peer_path = f"{peer_kind}.{peer_rel_name}"
            err_msg = f"Cannot delete {peers_data.source_kind} '{peers_data.source_id}'."
            err_msg += f" It is linked to mandatory relationship {peer_rel_name} on node {peer_kind} '{peers_data.destination_id}'"
            validation_errors.append(ValidationError({peer_path: err_msg}))

        return ValidationError(validation_errors)
