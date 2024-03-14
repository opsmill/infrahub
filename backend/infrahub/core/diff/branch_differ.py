from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Union

from typing_extensions import Self

from infrahub.core.constants import (
    BranchSupportType,
    DiffAction,
    InfrahubKind,
    PathType,
    RelationshipCardinality,
    RelationshipStatus,
)
from infrahub.core.manager import NodeManager
from infrahub.core.query.diff import (
    DiffAttributeQuery,
    DiffNodePropertiesByIDSQuery,
    DiffNodeQuery,
    DiffRelationshipPropertiesByIDSRangeQuery,
    DiffRelationshipPropertyQuery,
    DiffRelationshipQuery,
)
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import (
    DiffFromRequiredOnDefaultBranchError,
    DiffRangeValidationError,
)
from infrahub.message_bus.messages import GitDiffNamesOnly, GitDiffNamesOnlyResponse

from .model import (
    BranchChanges,
    DataConflict,
    DiffSummaryElement,
    FileDiffElement,
    ModifiedPath,
    NodeAttributeDiffElement,
    NodeDiffElement,
    PropertyDiffElement,
    RelationshipDiffElement,
    RelationshipEdgeNodeDiffElement,
    RelationshipPath,
    ValueElement,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

    from ..branch import Branch
    from ..node import Node


#  pylint: disable=too-many-branches,too-many-statements,too-many-lines


class BranchDiffer:
    diff_from: Timestamp
    diff_to: Timestamp

    def __init__(
        self,
        branch: Branch,
        origin_branch: Optional[Branch] = None,
        branch_only: bool = False,
        diff_from: Optional[Union[str, Timestamp]] = None,
        diff_to: Optional[Union[str, Timestamp]] = None,
        namespaces_include: Optional[List[str]] = None,
        namespaces_exclude: Optional[List[str]] = None,
        kinds_include: Optional[List[str]] = None,
        kinds_exclude: Optional[List[str]] = None,
        branch_support: Optional[List[BranchSupportType]] = None,
        db: Optional[InfrahubDatabase] = None,
        service: Optional[InfrahubServices] = None,
    ):
        """_summary_

        Args:
            branch (Branch): Main branch this diff is caculated from
            origin_branch (Branch): Storing the origin branch the main branch started from for convenience.
            branch_only (bool, optional): When True, only consider the changes in the branch, ignore the changes in main. Defaults to False.
            diff_from (Union[str, Timestamp], optional): Time from when the diff is calculated. Defaults to None.
            diff_to (Union[str, Timestamp], optional): Time to when the diff is calculated. Defaults to None.

        Raises:
            ValueError: if diff_from and diff_to are not correct
        """

        self.branch = branch
        self.branch_only = branch_only
        self.origin_branch = origin_branch

        self._db = db
        self._service = service

        self.namespaces_include = namespaces_include
        self.namespaces_exclude = namespaces_exclude
        self.kinds_include = kinds_include
        self.kinds_exclude = kinds_exclude
        self.branch_support = branch_support or [BranchSupportType.AWARE]

        if not diff_from and self.branch.is_default:
            raise DiffFromRequiredOnDefaultBranchError(
                f"diff_from is mandatory when diffing on the default branch `{self.branch.name}`."
            )

        # If diff from hasn't been provided, we'll use the creation of the branch as the starting point
        if diff_from:
            self.diff_from = Timestamp(diff_from)
        else:
            self.diff_from = Timestamp(self.branch.created_at)

        # If diff_to hasn't been provided, we will use the current time.
        self.diff_to = Timestamp(diff_to)

        if self.diff_to < self.diff_from:
            raise DiffRangeValidationError("diff_to must be later than diff_from")

        # Results organized by Branch
        self._results: Dict[str, dict] = defaultdict(
            lambda: {"nodes": {}, "rels": defaultdict(lambda: {}), "files": {}}
        )

        self._calculated_diff_nodes_at: Optional[Timestamp] = None
        self._calculated_diff_rels_at: Optional[Timestamp] = None
        self._calculated_diff_files_at: Optional[Timestamp] = None

    @property
    def service(self) -> InfrahubServices:
        if not self._service:
            raise ValueError("BranchDiffer object was not initialized with InfrahubServices")
        return self._service

    @property
    def db(self) -> InfrahubDatabase:
        if not self._db:
            raise ValueError("BranchDiffer object was not initialized with InfrahubDatabase")
        return self._db

    @classmethod
    async def init(
        cls,
        db: InfrahubDatabase,
        branch: Branch,
        branch_only: bool = False,
        diff_from: Optional[Union[str, Timestamp]] = None,
        diff_to: Optional[Union[str, Timestamp]] = None,
        namespaces_include: Optional[List[str]] = None,
        namespaces_exclude: Optional[List[str]] = None,
        kinds_include: Optional[List[str]] = None,
        kinds_exclude: Optional[List[str]] = None,
        branch_support: Optional[List[BranchSupportType]] = None,
        service: Optional[InfrahubServices] = None,
    ) -> Self:
        origin_branch = branch.get_origin_branch()

        return cls(
            branch=branch,
            origin_branch=origin_branch,
            branch_only=branch_only,
            diff_from=diff_from,
            diff_to=diff_to,
            namespaces_include=namespaces_include,
            namespaces_exclude=namespaces_exclude,
            kinds_include=kinds_include,
            kinds_exclude=kinds_exclude,
            branch_support=branch_support,
            db=db,
            service=service,
        )

    async def has_conflict(
        self,
    ) -> bool:
        """Return True if the same path has been modified on multiple branches. False otherwise"""

        return await self.has_conflict_graph()

    async def has_conflict_graph(self) -> bool:
        """Return True if the same path has been modified on multiple branches. False otherwise"""

        if await self.get_conflicts_graph():
            return True

        return False

    async def get_summaries_by_branch_and_id(self) -> Dict[str, Dict[str, DiffSummaryElement]]:
        """Return a list of changed nodes and associated actions

        If only a relationship is modified for a given node it will have the updated action.
        """
        nodes = await self.get_nodes()
        relationships = await self.get_relationships()
        changes: Dict[str, Dict[str, DiffSummaryElement]] = {}

        for branch_name, branch_nodes in nodes.items():
            if branch_name not in changes:
                changes[branch_name] = {}
            for node_id, node_diff in branch_nodes.items():
                if node_id not in changes[branch_name]:
                    changes[branch_name][node_id] = DiffSummaryElement(
                        branch=branch_name, node=node_id, kind=node_diff.kind, actions=[node_diff.action]
                    )
                if node_diff.action not in changes[branch_name][node_id].actions:
                    changes[branch_name][node_id].actions.append(node_diff.action)

        for branch_name, branch_relationships in relationships.items():
            if branch_name not in changes:
                changes[branch_name] = {}
            for relationship_type in branch_relationships.values():
                for relationship in relationship_type.values():
                    for rel_node in relationship.nodes.values():
                        if rel_node.id not in changes[branch_name]:
                            changes[branch_name][rel_node.id] = DiffSummaryElement(
                                branch=branch_name, node=rel_node.id, kind=rel_node.kind, actions=[DiffAction.UPDATED]
                            )
        return changes

    async def get_summary(self) -> List[DiffSummaryElement]:
        changes = await self.get_summaries_by_branch_and_id()
        summary = []
        for branch_diff in changes.values():
            for entry in branch_diff.values():
                summary.append(entry)

        return summary

    async def get_schema_summary(self) -> Dict[str, List[DiffSummaryElement]]:
        """Return a list of DiffSummaryElement for SchemaNode organized per Branch."""
        summary: Dict[str, List[DiffSummaryElement]] = defaultdict(list)
        for element in await self.get_summary():
            if element.kind == "SchemaNode":
                summary[element.branch].append(element)
        return summary

    async def has_schema_changes(self, branch: Optional[str] = None) -> bool:
        schema_summary = await self.get_schema_summary()
        if (branch and branch in schema_summary) or (not branch and schema_summary):
            return True

        return False

    async def get_conflicts(self) -> List[DataConflict]:
        """Return the list of conflicts identified by the diff as Path (tuple).

        For now we are not able to identify clearly enough the conflicts for the git repositories so this part is ignored.
        """
        return await self.get_conflicts_graph()

    async def get_conflicts_graph(self) -> List[DataConflict]:
        if self.branch_only:
            return []

        paths = await self.get_modified_paths_graph()

        # For now we assume that we can only have 2 branches but in the future we might need to support more
        branches = list(paths.keys())

        # if we don't have at least 2 branches returned we can safely assumed there is no conflict
        if len(branches) < 2:
            return []

        # Since we have 2 sets or tuple, we can quickly calculate the intersection using set(A) & set(B)
        conflicts = paths[branches[0]] & paths[branches[1]]

        branch0 = {str(conflict): conflict for conflict in paths[branches[0]]}
        branch1 = {str(conflict): conflict for conflict in paths[branches[1]]}
        changes = {branches[0]: branch0, branches[1]: branch1}
        responses = []
        for conflict in conflicts:
            response = DataConflict(
                name=conflict.element_name or "",
                type=conflict.type,
                id=conflict.node_id,
                kind=conflict.kind,
                path=str(conflict),
                change_type=conflict.change_type,
                conflict_path=conflict.conflict_path,
                path_type=conflict.path_type,
                property_name=conflict.property_name,
            )
            for branch, change in changes.items():
                if response.path in change and change[response.path]:
                    response.changes.append(
                        BranchChanges(
                            branch=branch,
                            action=change[response.path].action,
                            new=change[response.path].change.new,  # type: ignore[union-attr]
                            previous=change[response.path].change.previous,  # type: ignore[union-attr]
                        )
                    )
            responses.append(response)
        return responses

    async def get_modified_paths_graph(self) -> Dict[str, Set[ModifiedPath]]:
        """Return a list of all the modified paths in the graph per branch.

        Path for a node : ("node", node_id, attr_name, prop_type)
        Path for a relationship : ("relationships", rel_name, rel_id, prop_type

        Returns:
            Dict[str, set]: Returns a dictionnary by branch with a set of paths
        """

        paths: Dict[str, Set[ModifiedPath]] = {}

        nodes = await self.get_nodes()
        for branch_name, node_data in nodes.items():
            if self.branch_only and branch_name != self.branch.name:
                continue

            if branch_name not in paths:
                paths[branch_name] = set()

            for node_id, node_diff in node_data.items():
                modified_path = ModifiedPath(
                    type="data", kind=node_diff.kind, node_id=node_id, action=node_diff.action, path_type=PathType.NODE
                )
                paths[branch_name].add(modified_path)
                for attr_name, attr in node_diff.attributes.items():
                    for prop_type, prop_value in attr.properties.items():
                        modified_path = ModifiedPath(
                            type="data",
                            kind=node_diff.kind,
                            node_id=node_id,
                            action=attr.action,
                            element_name=attr_name,
                            path_type=PathType.ATTRIBUTE,
                            property_name=prop_type,
                            change=prop_value.value,
                        )
                        paths[branch_name].add(modified_path)

        relationships = await self.get_relationships()
        cardinality_one_branch_relationships: Dict[str, List[ModifiedPath]] = {}
        branch_kind_node: Dict[str, Dict[str, List[str]]] = {}
        display_label_map: Dict[str, Dict[str, str]] = {}
        kind_map: Dict[str, Dict[str, str]] = {}
        for branch_name in relationships.keys():
            branch_kind_node[branch_name] = {}
            cardinality_one_branch_relationships[branch_name] = []
            display_label_map[branch_name] = {}
            kind_map[branch_name] = {}

        for branch_name, rel_data in relationships.items():  # pylint: disable=too-many-nested-blocks
            cardinality_one_relationships: Dict[str, ModifiedPath] = {}
            if self.branch_only and branch_name != self.branch.name:
                continue

            if branch_name not in paths:
                paths[branch_name] = set()

            for rel_name, rels in rel_data.items():
                for _, rel in rels.items():
                    for node_id in rel.nodes:
                        neighbor_id = [neighbor for neighbor in rel.nodes.keys() if neighbor != node_id][0]
                        schema = registry.schema.get(name=rel.nodes[node_id].kind, branch=branch_name)
                        matching_relationship = [r for r in schema.relationships if r.identifier == rel_name]
                        if (
                            matching_relationship
                            and matching_relationship[0].cardinality == RelationshipCardinality.ONE
                        ):
                            relationship_key = f"{node_id}/{matching_relationship[0].name}"
                            if relationship_key not in cardinality_one_relationships:
                                cardinality_one_relationships[relationship_key] = ModifiedPath(
                                    type="data",
                                    node_id=node_id,
                                    action=DiffAction.UNCHANGED,
                                    kind=schema.kind,
                                    element_name=matching_relationship[0].name,
                                    path_type=PathType.from_relationship(matching_relationship[0].cardinality),
                                    change=ValueElement(),
                                )
                            peer_kind = matching_relationship[0].peer
                            if peer_kind not in branch_kind_node[branch_name]:
                                branch_kind_node[branch_name][peer_kind] = []
                            if rel.action == DiffAction.ADDED:
                                neighbor_id1 = rel.get_node_id_by_kind(kind=peer_kind)
                                if neighbor_id1:
                                    cardinality_one_relationships[relationship_key].change.new = neighbor_id1  # type: ignore[union-attr]
                                    branch_kind_node[branch_name][peer_kind].append(neighbor_id1)
                            elif rel.action == DiffAction.REMOVED:
                                neighbor_id2 = rel.get_node_id_by_kind(kind=peer_kind)
                                if neighbor_id2:
                                    cardinality_one_relationships[relationship_key].change.previous = neighbor_id2  # type: ignore[union-attr]
                                    branch_kind_node[branch_name][peer_kind].append(neighbor_id2)
                            if (
                                cardinality_one_relationships[relationship_key].change.previous  # type: ignore[union-attr]
                                != cardinality_one_relationships[relationship_key].change.new  # type: ignore[union-attr]
                            ):
                                cardinality_one_relationships[relationship_key].action = DiffAction.UPDATED
                        for prop_type, prop_value in rel.properties.items():
                            if matching_relationship:
                                modified_path = ModifiedPath(
                                    type="data",
                                    node_id=node_id,
                                    kind=schema.kind,
                                    action=rel.action,
                                    element_name=matching_relationship[0].name,
                                    path_type=PathType.from_relationship(matching_relationship[0].cardinality),
                                    property_name=prop_type,
                                    peer_id=neighbor_id,
                                    change=prop_value.value,
                                )
                                paths[branch_name].add(modified_path)

            for entry in cardinality_one_relationships.values():
                cardinality_one_branch_relationships[branch_name].append(entry)

        for branch_name, entries in branch_kind_node.items():
            for kind, ids in entries.items():
                schema = registry.schema.get(name=kind, branch=branch_name)
                fields = schema.generate_fields_for_display_label()
                query_nodes = await NodeManager.get_many(ids=ids, fields=fields, db=self.db, branch=branch_name)
                for node_id, node in query_nodes.items():
                    display_label_map[branch_name][node_id] = await node.render_display_label(db=self.db)
                    kind_map[branch_name][node_id] = kind

            for relationship in cardinality_one_branch_relationships[branch_name]:
                if relationship.change and relationship.change.new and relationship.change.previous:
                    if mapped_name := display_label_map[branch_name].get(relationship.change.new):
                        relationship.change.new = {
                            "id": relationship.change.new,
                            "display_label": mapped_name,
                            "kind": kind_map[branch_name].get(relationship.change.new),
                        }
                    if mapped_name := display_label_map[branch_name].get(relationship.change.previous):
                        relationship.change.previous = {
                            "id": relationship.change.previous,
                            "display_label": mapped_name,
                            "kind": kind_map[branch_name].get(relationship.change.previous),
                        }
                if relationship.action != DiffAction.UNCHANGED:
                    paths[branch_name].add(relationship)

        return paths

    async def get_nodes(self) -> Dict[str, Dict[str, NodeDiffElement]]:
        """Return all the nodes calculated by the diff, organized by branch."""

        if not self._calculated_diff_nodes_at:
            await self._calculate_diff_nodes()

        return {
            branch_name: data["nodes"]
            for branch_name, data in self._results.items()
            if not self.branch_only or branch_name == self.branch.name
        }

    async def _calculate_diff_nodes(self) -> None:
        """Calculate the diff for all the nodes and attributes.

        The results will be stored in self._results organized by branch.
        """
        # ------------------------------------------------------------
        # Process nodes that have been Added or Removed first
        # ------------------------------------------------------------
        query_nodes = await DiffNodeQuery.init(
            db=self.db,
            branch=self.branch,
            diff_from=self.diff_from,
            diff_to=self.diff_to,
            namespaces_include=self.namespaces_include,
            namespaces_exclude=self.namespaces_exclude,
            kinds_include=self.kinds_include,
            kinds_exclude=self.kinds_exclude,
            branch_support=self.branch_support,
        )
        await query_nodes.execute(db=self.db)

        for result in query_nodes.get_results():
            node_id = result.get("n").get("uuid")

            node_to = None
            if result.get("r").get("to"):
                node_to = Timestamp(result.get("r").get("to"))

            # If to_time is defined and is smaller than the diff_to time,
            #   then this is not the correct relationship to define this node
            #   NOTE would it make sense to move this logic into the Query itself ?
            if node_to and node_to < self.diff_to:
                continue

            branch_status = result.get("r").get("status")
            branch_name = result.get("r").get("branch")
            from_time = result.get("r").get("from")

            item = {
                "branch": result.get("r").get("branch"),
                "labels": sorted(list(result.get_node("n").labels)),
                "kind": result.get("n").get("kind"),
                "id": node_id,
                "db_id": result.get("n").element_id,
                "path": f"data/{node_id}",
                "attributes": {},
                "rel_id": result.get("r").element_id,
                "changed_at": Timestamp(from_time),
            }

            if branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED
            elif branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED

            self._results[branch_name]["nodes"][node_id] = NodeDiffElement(**item)

        # ------------------------------------------------------------
        # Process Attributes that have been Added, Updated or Removed
        #  We don't process the properties right away, instead we'll identify the node that mostlikely already exist
        #  and we'll query the current value to fully understand what we need to do with it.
        # ------------------------------------------------------------
        attrs_to_query = set()
        query_attrs = await DiffAttributeQuery.init(
            db=self.db,
            branch=self.branch,
            diff_from=self.diff_from,
            diff_to=self.diff_to,
            namespaces_include=self.namespaces_include,
            namespaces_exclude=self.namespaces_exclude,
            kinds_include=self.kinds_include,
            kinds_exclude=self.kinds_exclude,
            branch_support=self.branch_support,
        )
        await query_attrs.execute(db=self.db)

        for result in query_attrs.get_results():
            node_id = result.get("n").get("uuid")
            branch_name = result.get("r2").get("branch")

            # Check if the node already exist, if not it means it was not added or removed so it was updated
            if node_id not in self._results[branch_name]["nodes"].keys():
                item = {
                    "labels": sorted(list(result.get_node("n").labels)),
                    "kind": result.get("n").get("kind"),
                    "id": node_id,
                    "db_id": result.get("n").element_id,
                    "path": f"data/{node_id}",
                    "attributes": {},
                    "changed_at": None,
                    "action": DiffAction.UPDATED,
                    "rel_id": None,
                    "branch": branch_name,
                }

                self._results[branch_name]["nodes"][node_id] = NodeDiffElement(**item)

            # Check if the Attribute is already present or if it was added during this time frame.
            attr_name = result.get("a").get("name")
            attr_id = result.get("a").get("uuid")
            if attr_name not in self._results[branch_name]["nodes"][node_id].attributes.keys():
                node = self._results[branch_name]["nodes"][node_id]
                item = {
                    "id": attr_id,
                    "db_id": result.get_node("a").element_id,
                    "name": attr_name,
                    "path": f"data/{node_id}/{attr_name}",
                    "rel_id": result.get_rel("r1").element_id,
                    "properties": {},
                    "origin_rel_id": None,
                }

                attr_to = None
                attr_from = None
                branch_status = result.get("r1").get("status")

                if result.get("r1").get("to"):
                    attr_to = Timestamp(result.get("r1").get("to"))
                if result.get("r1").get("from"):
                    attr_from = Timestamp(result.get("r1").get("from"))

                if attr_to and attr_to < self.diff_to:
                    continue

                if (
                    node.action in [DiffAction.ADDED, DiffAction.UPDATED]
                    and attr_from >= self.diff_from
                    and branch_status == RelationshipStatus.ACTIVE.value
                ):
                    item["action"] = DiffAction.ADDED
                    item["changed_at"] = attr_from

                elif attr_from >= self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                    item["action"] = DiffAction.REMOVED
                    item["changed_at"] = attr_from

                    attrs_to_query.add(attr_id)
                else:
                    item["action"] = DiffAction.UPDATED
                    item["changed_at"] = None

                    attrs_to_query.add(attr_id)

                self._results[branch_name]["nodes"][node_id].attributes[attr_name] = NodeAttributeDiffElement(**item)

        # ------------------------------------------------------------
        # Query the current value for all attributes that have been updated
        # ------------------------------------------------------------
        origin_attr_query = await DiffNodePropertiesByIDSQuery.init(
            db=self.db,
            ids=list(attrs_to_query),
            branch=self.branch,
            at=self.diff_from,
        )

        await origin_attr_query.execute(db=self.db)

        for result in query_attrs.get_results():
            node_id = result.get("n").get("uuid")
            branch_name = result.get("r2").get("branch")
            branch_status = result.get("r2").get("status")
            attr_id = result.get("a").get("uuid")
            attr_name = result.get("a").get("name")
            prop_type = result.get_rel("r2").type

            origin_attr = origin_attr_query.get_results_by_id_and_prop_type(attr_id=attr_id, prop_type=prop_type)

            # Process the Property of the Attribute
            prop_to = None
            prop_from = None

            if result.get("r2").get("to"):
                prop_to = Timestamp(result.get("r2").get("to"))
            if result.get("r2").get("from"):
                prop_from = Timestamp(result.get("r2").get("from"))

            if prop_to and prop_to < self.diff_to:
                continue

            path = f"data/{node_id}/{attr_name}/property/{prop_type}"
            if prop_type == "HAS_VALUE":
                path = f"data/{node_id}/{attr_name}/value"

            item = {
                "type": prop_type,
                "branch": branch_name,
                "path": path,
                "db_id": result.get("ap").element_id,
                "rel_id": result.get("r2").element_id,
                "origin_rel_id": None,
                "value": {"new": result.get("ap").get("value"), "previous": None},
            }

            if origin_attr:
                item["origin_rel_id"] = origin_attr[0].get("r").element_id
                item["value"]["previous"] = origin_attr[0].get("ap").get("value")

            if not origin_attr and prop_from >= self.diff_from and branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED
                item["changed_at"] = prop_from
            elif prop_from >= self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED
                item["changed_at"] = prop_from
            else:
                item["action"] = DiffAction.UPDATED
                item["changed_at"] = prop_from

            self._results[branch_name]["nodes"][node_id].attributes[attr_name].origin_rel_id = result.get(
                "r1"
            ).element_id
            self._results[branch_name]["nodes"][node_id].attributes[attr_name].properties[
                prop_type
            ] = PropertyDiffElement(**item)

        self._calculated_diff_nodes_at = Timestamp()

    async def get_relationships(self) -> Dict[str, Dict[str, Dict[str, RelationshipDiffElement]]]:
        if not self._calculated_diff_rels_at:
            await self._calculated_diff_rels()

        return {
            branch_name: data["rels"]
            for branch_name, data in self._results.items()
            if not self.branch_only or branch_name == self.branch.name
        }

    async def get_relationships_per_node(self) -> Dict[str, Dict[str, Dict[str, List[RelationshipDiffElement]]]]:
        rels = await self.get_relationships()

        # Organize the Relationships data per node and per relationship name in order to simplify the association with the nodes Later on.
        rels_per_node: Dict[str, Dict[str, Dict[str, List[RelationshipDiffElement]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        for branch_name, items in rels.items():
            for item in items.values():
                for sub_item in item.values():
                    for node_id, _ in sub_item.nodes.items():
                        rels_per_node[branch_name][node_id][sub_item.name].append(sub_item)

        return rels_per_node

    async def get_node_id_per_kind(self) -> Dict[str, Dict[str, List[str]]]:
        # Node IDs organized per Branch and per Kind
        rels = await self.get_relationships()
        nodes = await self.get_nodes()

        node_ids: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

        for branch_name, rel_items in rels.items():
            for rel_item in rel_items.values():
                for sub_item in rel_item.values():
                    for node_id, node in sub_item.nodes.items():
                        if node_id not in node_ids[branch_name][node.kind]:
                            node_ids[branch_name][node.kind].append(node_id)

        # Extract the id of all nodes ahead of time in order to query all display labels
        for branch_name, node_items in nodes.items():
            for node_item in node_items.values():
                if node_item.id not in node_ids[branch_name][node_item.kind]:
                    node_ids[branch_name][node_item.kind].append(node_item.id)

        return node_ids

    async def _calculated_diff_rels(self) -> None:
        """Calculate the diff for all the relationships between Nodes.

        The results will be stored in self._results organized by branch.
        """

        rel_ids_to_query = []

        # ------------------------------------------------------------
        # Process first the main path of the relationships
        #   to identify the relationship that have been ADDED or DELETED
        # ------------------------------------------------------------
        query_rels = await DiffRelationshipQuery.init(
            db=self.db,
            branch=self.branch,
            diff_from=self.diff_from,
            diff_to=self.diff_to,
            namespaces_include=self.namespaces_include,
            namespaces_exclude=self.namespaces_exclude,
            kinds_include=self.kinds_include,
            kinds_exclude=self.kinds_exclude,
            branch_support=self.branch_support,
        )
        await query_rels.execute(db=self.db)

        for result in query_rels.get_results():
            branch_name = result.get("r1").get("branch")
            branch_status = result.get("r1").get("status")
            rel_name = result.get("rel").get("name")
            rel_id = result.get("rel").get("uuid")

            src_node_id = result.get("sn").get("uuid")
            dst_node_id = result.get("dn").get("uuid")

            from_time = Timestamp(result.get("r1").get("from"))
            # to_time = result.get("r1").get("to", None)

            item = {
                "branch": branch_name,
                "id": rel_id,
                "db_id": result.get("rel").element_id,
                "name": rel_name,
                "nodes": {
                    src_node_id: RelationshipEdgeNodeDiffElement(
                        id=src_node_id,
                        db_id=result.get("sn").element_id,
                        rel_id=result.get("r1").element_id,
                        labels=sorted(result.get_node("sn").labels),
                        kind=result.get("sn").get("kind"),
                    ),
                    dst_node_id: RelationshipEdgeNodeDiffElement(
                        id=dst_node_id,
                        db_id=result.get("dn").element_id,
                        rel_id=result.get("r2").element_id,
                        labels=sorted(result.get_node("dn").labels),
                        kind=result.get("dn").get("kind"),
                    ),
                },
                "properties": {},
            }

            relationship_paths = self.parse_relationship_paths(
                nodes=item["nodes"], branch_name=branch_name, relationship_name=rel_name
            )
            item["paths"] = relationship_paths.paths
            item["conflict_paths"] = relationship_paths.conflict_paths

            # FIXME Need to revisit changed_at, mostlikely not accurate. More of a placeholder at this point
            if branch_status == RelationshipStatus.ACTIVE.value:
                item["action"] = DiffAction.ADDED
                item["changed_at"] = from_time
            elif branch_status == RelationshipStatus.DELETED.value:
                item["action"] = DiffAction.REMOVED
                item["changed_at"] = from_time
                rel_ids_to_query.append(rel_id)
            else:
                raise ValueError(f"Unexpected value for branch_status: {branch_status}")

            self._results[branch_name]["rels"][rel_name][rel_id] = RelationshipDiffElement(**item)

        # ------------------------------------------------------------
        # Then Query & Process the properties of the relationships
        #  First we need to need to create the RelationshipDiffElement that haven't been created previously
        #  Then we can process the properties themselves
        # ------------------------------------------------------------
        query_props = await DiffRelationshipPropertyQuery.init(
            db=self.db, branch=self.branch, diff_from=self.diff_from, diff_to=self.diff_to
        )
        await query_props.execute(db=self.db)

        for result in query_props.get_results():
            branch_name = result.get("r3").get("branch")
            branch_status = result.get("r3").get("status")
            rel_name = result.get("rel").get("name")
            rel_id = result.get("rel").get("uuid")

            # Check if the relationship already exist, if not we need to create it
            if rel_id in self._results[branch_name]["rels"][rel_name]:
                continue

            src_node_id = result.get("sn").get("uuid")
            dst_node_id = result.get("dn").get("uuid")

            item = {
                "id": rel_id,
                "db_id": result.get("rel").element_id,
                "name": rel_name,
                "nodes": {
                    src_node_id: RelationshipEdgeNodeDiffElement(
                        id=src_node_id,
                        db_id=result.get("sn").element_id,
                        rel_id=result.get("r1").element_id,
                        kind=result.get("sn").get("kind"),
                        labels=sorted(result.get_node("sn").labels),
                    ),
                    dst_node_id: RelationshipEdgeNodeDiffElement(
                        id=dst_node_id,
                        db_id=result.get_node("dn").element_id,
                        rel_id=result.get("r2").element_id,
                        kind=result.get_node("dn").get("kind"),
                        labels=sorted(result.get_node("dn").labels),
                    ),
                },
                "properties": {},
                "action": DiffAction.UPDATED,
                "changed_at": None,
                "branch": branch_name,
            }
            relationship_paths = self.parse_relationship_paths(
                nodes=item["nodes"], branch_name=branch_name, relationship_name=rel_name
            )
            item["paths"] = relationship_paths.paths
            item["conflict_paths"] = relationship_paths.conflict_paths

            self._results[branch_name]["rels"][rel_name][rel_id] = RelationshipDiffElement(**item)

            rel_ids_to_query.append(rel_id)

        # ------------------------------------------------------------
        # Query the current value of the relationships that have been flagged
        #  Usually we need more information to determine if the rel has been updated, added or removed
        # ------------------------------------------------------------
        origin_rel_properties_query = await DiffRelationshipPropertiesByIDSRangeQuery.init(
            db=self.db,
            ids=rel_ids_to_query,
            branch=self.branch,
            diff_from=self.diff_from,
            diff_to=self.diff_to,
        )
        await origin_rel_properties_query.execute(db=self.db)

        for result in query_props.get_results():
            branch_name = result.get("r3").get("branch")
            branch_status = result.get("r3").get("status")
            rel_name = result.get("rel").get("name")
            rel_id = result.get("rel").get("uuid")

            prop_type = result.get_rel("r3").type
            prop_from = Timestamp(result.get("r3").get("from"))

            origin_prop = origin_rel_properties_query.get_results_by_id_and_prop_type(
                rel_id=rel_id, prop_type=prop_type
            )

            prop = {
                "type": prop_type,
                "branch": branch_name,
                "db_id": result.get("rp").element_id,
                "rel_id": result.get("r3").element_id,
                "origin_rel_id": None,
                "value": {"new": result.get("rp").get("value"), "previous": None},
            }

            if origin_prop:
                prop["origin_rel_id"] = origin_prop[0].get("r").element_id
                prop["value"]["previous"] = origin_prop[0].get("rp").get("value")

            if not origin_prop and prop_from >= self.diff_from and branch_status == RelationshipStatus.ACTIVE.value:
                prop["action"] = DiffAction.ADDED
                prop["changed_at"] = prop_from
            elif prop_from >= self.diff_from and branch_status == RelationshipStatus.DELETED.value:
                prop["action"] = DiffAction.REMOVED
                prop["changed_at"] = prop_from
            else:
                prop["action"] = DiffAction.UPDATED
                prop["changed_at"] = prop_from

            self._results[branch_name]["rels"][rel_name][rel_id].properties[prop_type] = PropertyDiffElement(**prop)

        self._calculated_diff_rels_at = Timestamp()

    @staticmethod
    def parse_relationship_paths(
        nodes: Dict[str, RelationshipEdgeNodeDiffElement], branch_name: str, relationship_name: str
    ) -> RelationshipPath:
        node_ids = list(nodes.keys())
        neighbor_map = {node_ids[0]: node_ids[1], node_ids[1]: node_ids[0]}
        relationship_paths = RelationshipPath()
        for relationship in nodes.values():
            schema = registry.schema.get(name=relationship.kind, branch=branch_name)
            matching_relationship = [r for r in schema.relationships if r.identifier == relationship_name]
            relationship_path_name = "-undefined-"
            if matching_relationship:
                relationship_path_name = matching_relationship[0].name
            relationship_paths.paths.append(
                f"data/{relationship.id}/{relationship_path_name}/{neighbor_map[relationship.id]}"
            )
            relationship_paths.conflict_paths.append(f"data/{relationship.id}/{relationship_path_name}/peer")

        return relationship_paths

    async def get_files(self) -> Dict[str, List[FileDiffElement]]:
        if not self._calculated_diff_files_at:
            await self._calculated_diff_files()

        return {
            branch_name: data["files"]
            for branch_name, data in self._results.items()
            if not self.branch_only or branch_name == self.branch.name
        }

    async def _calculated_diff_files(self) -> None:
        self._results[self.branch.name]["files"] = await self.get_files_repositories_for_branch(branch=self.branch)

        if self.origin_branch:
            self._results[self.origin_branch.name]["files"] = await self.get_files_repositories_for_branch(
                branch=self.origin_branch
            )

        self._calculated_diff_files_at = Timestamp()

    async def get_files_repository(
        self,
        branch_name: str,
        repository: Node,
        commit_from: str,
        commit_to: str,
    ) -> List[FileDiffElement]:
        """Return all the files that have added, changed or removed for a given repository between 2 commits."""

        files = []

        message = GitDiffNamesOnly(
            repository_id=repository.id,
            repository_name=repository.name.value,  # type: ignore[attr-defined]
            repository_kind=repository.get_kind(),
            first_commit=commit_from,
            second_commit=commit_to,
        )

        reply = await self.service.message_bus.rpc(message=message, response_class=GitDiffNamesOnlyResponse)
        diff = reply.data

        actions = {
            "files_changed": DiffAction.UPDATED,
            "files_added": DiffAction.ADDED,
            "files_removed": DiffAction.REMOVED,
        }

        for action_name, diff_action in actions.items():
            for filename in getattr(diff, action_name, []):
                files.append(
                    FileDiffElement(
                        branch=branch_name,
                        location=filename,
                        repository=repository.id,
                        action=diff_action,
                        commit_to=commit_to,
                        commit_from=commit_from,
                    )
                )

        return files

    async def get_files_repositories_for_branch(self, branch: Branch) -> List[FileDiffElement]:
        tasks = []
        files = []

        repos_to = {
            repo.id: repo
            for repo in await NodeManager.query(
                schema=InfrahubKind.GENERICREPOSITORY, db=self.db, branch=branch, at=self.diff_to
            )
        }
        repos_from = {
            repo.id: repo
            for repo in await NodeManager.query(
                schema=InfrahubKind.GENERICREPOSITORY, db=self.db, branch=branch, at=self.diff_from
            )
        }

        # For now we are ignoring the repos that are either not present at to time or at from time.
        # These repos will be identified in the graph already
        repo_ids_common = set(repos_to.keys()) & set(repos_from.keys())

        for repo_id in repo_ids_common:
            if repos_to[repo_id].commit.value == repos_from[repo_id].commit.value:  # type: ignore[attr-defined]
                continue

            tasks.append(
                self.get_files_repository(
                    branch_name=branch.name,
                    repository=repos_to[repo_id],
                    commit_from=repos_from[repo_id].commit.value,  # type: ignore[attr-defined]
                    commit_to=repos_to[repo_id].commit.value,  # type: ignore[attr-defined]
                )
            )

        responses = await asyncio.gather(*tasks)

        for response in responses:
            if isinstance(response, list):
                files.extend(response)

        return files
