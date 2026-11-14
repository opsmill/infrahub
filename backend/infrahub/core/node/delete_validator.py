from collections import defaultdict
from collections.abc import Iterable, Mapping
from enum import Enum

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
    BranchSupportType,
    RelationshipDeleteBehavior,
    RelationshipDirection,
)
from infrahub.core.node import Node
from infrahub.core.query.node_delete import (
    DeleteSetNode,
    LinkPattern,
    NodeDeleteCascadeQuery,
    NodeDeleteCascadeQueryResult,
    NodeDeleteOtherBranchesQuery,
    RequiredPeerLink,
    RequiredPeerLinkOnBranches,
)
from infrahub.core.schema import MainSchemaTypes, NodeSchema, ProfileSchema, TemplateSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError

CASCADE_LEVELS_PER_QUERY_WITH_LOOP = 10
"""The cascade levels one query follows when cascades can loop, so a longer chain takes one query per this many."""


class DeleteRelationshipType(Enum):
    CASCADE_DELETE = "cascade"
    DEPENDENT_NODE = "dependent"


def _get_peer_relationship_name(peer_schema: MainSchemaTypes | None, link: RequiredPeerLink) -> str:
    """Return the name of the peer's relationship that holds `link`, or its identifier when the schema lacks it."""
    if peer_schema is not None:
        for relationship in peer_schema.get_relationships_by_identifier(id=link.identifier):
            if relationship.direction == link.direction.neighbor_direction:
                return relationship.name
    return link.identifier


def _format_branch_names(branch_names: Iterable[str]) -> str:
    sorted_names = sorted(branch_names)
    quoted_names = ", ".join(f"'{branch_name}'" for branch_name in sorted_names)
    if len(sorted_names) == 1:
        return f"branch {quoted_names}"
    return f"branches {quoted_names}"


class NodeDeleteIndex:
    def __init__(self, all_schemas_map: Mapping[str, MainSchemaTypes]) -> None:
        self._all_schemas_map = all_schemas_map
        self._link_patterns: defaultdict[DeleteRelationshipType, set[LinkPattern]] = defaultdict(set)

    def index(self, start_schemas: Iterable[NodeSchema | ProfileSchema | TemplateSchema]) -> None:
        cascade_kinds = self._index_cascading_deletes(start_schemas=start_schemas)
        self.index_dependent_links(deleted_kinds=cascade_kinds)

    def _get_schema_kinds(self, schema_kind: str) -> set[str]:
        schema = self._all_schemas_map[schema_kind]
        if schema.is_node_schema:
            return {schema_kind}
        used_by = getattr(schema, "used_by", None)
        if schema.is_generic_schema and used_by:
            return set(used_by)
        return set()

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
                self._link_patterns[DeleteRelationshipType.CASCADE_DELETE].update(
                    LinkPattern(
                        kind=kind_to_check,
                        identifier=relationship_schema.get_identifier(),
                        direction=relationship_schema.direction,
                        peer_kind=peer_kind,
                    )
                    for peer_kind in peer_kinds
                )
                for peer_kind in peer_kinds:
                    if peer_kind not in visited:
                        kinds_to_check.add(peer_kind)
        return visited

    def index_dependent_links(self, deleted_kinds: set[str], skip_cascading: bool = False) -> None:
        """Index the links of a required relationship to one of `deleted_kinds`, from the deleted node's side.

        With `skip_cascading`, a link is left out when the deleted kind cascades on that relationship. The match
        ignores the peer kind, because a required relationship can be declared on a generic of the cascade's peers.
        """
        deleted_kinds_and_generics = set(deleted_kinds)
        for kind in deleted_kinds:
            schema = self._all_schemas_map.get(kind)
            if isinstance(schema, (NodeSchema, ProfileSchema, TemplateSchema)):
                deleted_kinds_and_generics.update(schema.inherit_from)
        cascading_relationships = self._get_cascading_relationships(kinds=deleted_kinds) if skip_cascading else set()
        for node_schema in self._all_schemas_map.values():
            for relationship_schema in node_schema.relationships:
                if relationship_schema.optional is True or relationship_schema.peer not in deleted_kinds_and_generics:
                    continue
                identifier = relationship_schema.get_identifier()
                direction = relationship_schema.direction.neighbor_direction
                self._link_patterns[DeleteRelationshipType.DEPENDENT_NODE].update(
                    LinkPattern(
                        kind=deleted_kind, identifier=identifier, direction=direction, peer_kind=node_schema.kind
                    )
                    for deleted_kind in self._get_schema_kinds(schema_kind=relationship_schema.peer) & deleted_kinds
                    if (deleted_kind, identifier, direction) not in cascading_relationships
                )

    def _get_cascading_relationships(self, kinds: Iterable[str]) -> set[tuple[str, str, RelationshipDirection]]:
        """Return the kind, identifier and direction of each relationship on which one of `kinds` cascades."""
        cascading_relationships: set[tuple[str, str, RelationshipDirection]] = set()
        for kind in kinds:
            schema = self._all_schemas_map.get(kind)
            if schema is None:
                continue
            cascading_relationships.update(
                (kind, relationship_schema.get_identifier(), relationship_schema.direction)
                for relationship_schema in schema.relationships
                if relationship_schema.on_delete == RelationshipDeleteBehavior.CASCADE
            )
        return cascading_relationships

    def get_link_patterns(self, relationship_type: DeleteRelationshipType) -> list[LinkPattern]:
        """Return the indexed links of `relationship_type`, from the deleted node's side."""
        return sorted(self._link_patterns.get(relationship_type, set()))

    def get_cascade_depth(self, start_kinds: Iterable[str]) -> int | None:
        """Return the number of links in the longest cascade from `start_kinds`, or None when a cascade can loop."""
        cascade_peer_kinds: defaultdict[str, set[str]] = defaultdict(set)
        for pattern in self.get_link_patterns(relationship_type=DeleteRelationshipType.CASCADE_DELETE):
            cascade_peer_kinds[pattern.kind].add(pattern.peer_kind)
        depth_by_kind: dict[str, int] = {}
        kinds_in_progress: set[str] = set()

        def get_depth(kind: str) -> int | None:
            if kind in depth_by_kind:
                return depth_by_kind[kind]
            if kind in kinds_in_progress:
                return None
            kinds_in_progress.add(kind)
            depth = 0
            for peer_kind in cascade_peer_kinds[kind]:
                peer_depth = get_depth(peer_kind)
                if peer_depth is None:
                    return None
                depth = max(depth, peer_depth + 1)
            kinds_in_progress.discard(kind)
            depth_by_kind[kind] = depth
            return depth

        max_depth = 0
        for kind in start_kinds:
            depth = get_depth(kind)
            if depth is None:
                return None
            max_depth = max(max_depth, depth)
        return max_depth


class NodeDeleteValidator:
    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch
        schema_branch = registry.schema.get_schema_branch(name=self.branch.name)
        self._all_schemas_map = schema_branch.get_all(duplicate=False)
        self.index: NodeDeleteIndex = NodeDeleteIndex(all_schemas_map=self._all_schemas_map)

    async def get_ids_to_delete(self, nodes: Iterable[Node], at: Timestamp | str | None = None) -> set[str]:
        """Return the ids of `nodes` and of every node a delete cascades to on the request branch.

        A branch-agnostic node is deleted on every live branch, so for those the check also covers every other live
        branch, where the branch-aware nodes of the delete set still exist.

        Raises:
            ValidationError: A peer outside the delete set has a required relationship to a node in it.

        """
        start_schemas = {node.get_schema() for node in nodes}
        self.index.index(start_schemas=start_schemas)
        at = Timestamp(at)
        start_ids = {node.get_id() for node in nodes}
        if not any(
            self.index.get_link_patterns(relationship_type=relationship_type)
            for relationship_type in DeleteRelationshipType
        ) and all(schema.branch != BranchSupportType.AGNOSTIC for schema in start_schemas):
            return start_ids
        request_window_name = registry.default_branch if self.branch.name == GLOBAL_BRANCH_NAME else self.branch.name

        delete_set = await self._get_delete_set(
            start_ids=start_ids,
            start_kinds={schema.kind for schema in start_schemas},
            request_window_name=request_window_name,
            at=at,
        )
        request_links = set(delete_set.required_links)
        blocking_branch_names: defaultdict[RequiredPeerLink, set[str]] = defaultdict(set)
        for link in request_links:
            blocking_branch_names[link].add(request_window_name)

        schemas_map_by_branch_name: dict[str, Mapping[str, MainSchemaTypes]] = {}
        agnostic_nodes = [node for node in delete_set.nodes if node.is_agnostic]
        if agnostic_nodes:
            links_on_other_branches, schemas_map_by_branch_name = await self._get_links_on_other_branches(
                agnostic_nodes=agnostic_nodes, request_window_name=request_window_name, at=at
            )
            for link_on_branches in links_on_other_branches:
                blocking_branch_names[link_on_branches.link].update(link_on_branches.branch_names)

        if blocking_branch_names:
            raise ValidationError(
                [
                    self._build_required_peer_error(
                        link=link,
                        schemas_map=self._all_schemas_map
                        if link in request_links
                        else schemas_map_by_branch_name.get(min(branch_names), {}),
                        branch_names=branch_names if agnostic_nodes else None,
                    )
                    for link, branch_names in sorted(blocking_branch_names.items())
                ]
            )
        return start_ids | {node.uuid for node in delete_set.nodes}

    async def _get_delete_set(
        self, start_ids: set[str], start_kinds: set[str], request_window_name: str, at: Timestamp
    ) -> NodeDeleteCascadeQueryResult:
        cascade_depth = self.index.get_cascade_depth(start_kinds=start_kinds)
        known_ids = sorted(start_ids)
        frontier_ids = known_ids
        while True:
            query = await NodeDeleteCascadeQuery.init(
                db=self.db,
                branch=self.branch,
                at=at,
                request_window_name=request_window_name,
                known_ids=known_ids,
                frontier_ids=frontier_ids,
                cascade_patterns=self.index.get_link_patterns(relationship_type=DeleteRelationshipType.CASCADE_DELETE),
                required_patterns=self.index.get_link_patterns(relationship_type=DeleteRelationshipType.DEPENDENT_NODE),
                levels=CASCADE_LEVELS_PER_QUERY_WITH_LOOP if cascade_depth is None else cascade_depth,
                levels_cover_cascade=cascade_depth is not None,
            )
            await query.execute(db=self.db)
            delete_set = query.get_data()
            if cascade_depth is not None or not delete_set.frontier_ids:
                return delete_set
            known_ids = [node.uuid for node in delete_set.nodes]
            frontier_ids = delete_set.frontier_ids

    async def _get_links_on_other_branches(
        self, agnostic_nodes: list[DeleteSetNode], request_window_name: str, at: Timestamp
    ) -> tuple[list[RequiredPeerLinkOnBranches], dict[str, Mapping[str, MainSchemaTypes]]]:
        """Return the required links to `agnostic_nodes` on each live branch other than the request branch.

        Each branch decides from its own schema which relationships are required, and leaves out a relationship on
        which the deleted node's kind cascades in that schema, because the cascade deletes on the request branch only
        and the peer stays on the other branch. The schema each branch was checked with is returned with the links,
        so an error names the relationship that schema declares.
        """
        agnostic_kinds = {node.kind for node in agnostic_nodes}
        patterns_by_schema_hash: dict[str, list[LinkPattern]] = {}
        required_patterns_by_branch: dict[str, list[LinkPattern]] = {}
        schemas_map_by_branch_name: dict[str, Mapping[str, MainSchemaTypes]] = {}
        for branch_name in registry.branch:
            if branch_name in {GLOBAL_BRANCH_NAME, request_window_name}:
                continue
            schema_branch = registry.schema.get_schema_branch(name=branch_name)
            schemas_map_by_branch_name[branch_name] = schema_branch.get_all(duplicate=False)
            schema_hash = schema_branch.get_hash()
            if schema_hash not in patterns_by_schema_hash:
                branch_index = NodeDeleteIndex(all_schemas_map=schemas_map_by_branch_name[branch_name])
                branch_index.index_dependent_links(deleted_kinds=agnostic_kinds, skip_cascading=True)
                patterns_by_schema_hash[schema_hash] = branch_index.get_link_patterns(
                    relationship_type=DeleteRelationshipType.DEPENDENT_NODE
                )
            if patterns_by_schema_hash[schema_hash]:
                required_patterns_by_branch[branch_name] = patterns_by_schema_hash[schema_hash]
        if not required_patterns_by_branch:
            return [], schemas_map_by_branch_name

        query = await NodeDeleteOtherBranchesQuery.init(
            db=self.db,
            branch=self.branch,
            at=at,
            request_window_name=request_window_name,
            agnostic_ids=sorted(node.uuid for node in agnostic_nodes),
            required_patterns_by_branch=required_patterns_by_branch,
        )
        await query.execute(db=self.db)
        return query.get_data(), schemas_map_by_branch_name

    @staticmethod
    def _build_required_peer_error(
        link: RequiredPeerLink, schemas_map: Mapping[str, MainSchemaTypes], branch_names: set[str] | None
    ) -> ValidationError:
        peer_rel_name = _get_peer_relationship_name(peer_schema=schemas_map.get(link.peer_kind), link=link)
        err_msg = f"Cannot delete {link.deleted_kind} '{link.deleted_id}'."
        err_msg += f" It is linked to mandatory relationship {peer_rel_name} on node {link.peer_kind} '{link.peer_id}'"
        if branch_names:
            err_msg += f" on {_format_branch_names(branch_names)}"
        return ValidationError({f"{link.peer_kind}.{peer_rel_name}": err_msg})
