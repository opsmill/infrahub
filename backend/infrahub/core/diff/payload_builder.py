from __future__ import annotations

import copy
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from infrahub.core import get_branch, registry
from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.log import get_logger

from .model import (
    BranchDiff,
    BranchDiffAttribute,
    BranchDiffElement,
    BranchDiffElementAttribute,
    BranchDiffElementRelationshipMany,
    BranchDiffElementRelationshipManyPeer,
    BranchDiffElementRelationshipOne,
    BranchDiffEntry,
    BranchDiffNode,
    BranchDiffProperty,
    BranchDiffPropertyCollection,
    BranchDiffRelationshipMany,
    BranchDiffRelationshipManyElement,
    BranchDiffRelationshipOne,
    BranchDiffRelationshipOnePeer,
    BranchDiffRelationshipOnePeerCollection,
    BranchDiffRelationshipOnePeerValue,
    BranchDiffRelationshipPeerNode,
    DiffElementType,
    EnrichedDiffSummaryElement,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

    from .branch_differ import BranchDiffer
    from .model import NodeDiffElement, RelationshipDiffElement


log = get_logger(__name__)


async def get_display_labels_per_kind(
    kind: str, ids: List[str], branch_name: str, db: InfrahubDatabase
) -> Dict[str, str]:
    """Return the display_labels of a list of nodes of a specific kind."""
    branch = await get_branch(branch=branch_name, db=db)
    schema = registry.schema.get(name=kind, branch=branch)
    fields = schema.generate_fields_for_display_label()
    nodes = await NodeManager.get_many(ids=ids, fields=fields, db=db, branch=branch)
    return {node_id: await node.render_display_label(db=db) for node_id, node in nodes.items()}


async def get_display_labels(nodes: Dict[str, Dict[str, List[str]]], db: InfrahubDatabase) -> Dict[str, Dict[str, str]]:
    """Query the display_labels of a group of nodes organized per branch and per kind."""
    response: Dict[str, Dict[str, str]] = {}
    for branch_name, items in nodes.items():
        if branch_name not in response:
            response[branch_name] = {}
        for kind, ids in items.items():
            labels = await get_display_labels_per_kind(kind=kind, ids=ids, db=db, branch_name=branch_name)
            response[branch_name].update(labels)

    return response


class DiffPayloadBuilder:
    def __init__(self, db: InfrahubDatabase, diff: BranchDiffer, kinds_to_include: Optional[List[str]] = None):
        self.db = db
        self.diff = diff
        self.kinds_to_include = kinds_to_include
        self.diffs: List[BranchDiffNode] = []
        self.entries: Dict[str, BranchDiffEntry] = {}
        self.rels_per_node: Dict[str, Dict[str, Dict[str, List[RelationshipDiffElement]]]] = {}
        self.display_labels: Dict[str, Dict[str, str]] = {}
        self.rels: Dict[str, Dict[str, Dict[str, RelationshipDiffElement]]] = {}
        self.nodes: Dict[str, Dict[str, NodeDiffElement]] = {}
        self.is_parsed: bool = False

    def _add_node_summary(self, branch_diff_node: BranchDiffNode, action: DiffAction) -> None:
        self.entries[branch_diff_node.id].summary.inc(action.value)
        branch_diff_node.summary.inc(action.value)

    def _set_display_label(self, node_id: str, branch: str, display_label: str) -> None:
        if not display_label:
            return
        self.entries[node_id].display_label[branch] = display_label

    def _get_branch_display_label_map(self, branch_name: str) -> Dict[str, str]:
        return self.display_labels.get(branch_name, {})

    def _get_node_display_label(self, branch_name: str, node_id: str) -> str:
        branch_display_label_map = self._get_branch_display_label_map(branch_name=branch_name)
        return branch_display_label_map.get(node_id, "")

    def _set_node_action(self, node_id: str, branch: str, action: DiffAction) -> None:
        self.entries[node_id].action[branch] = action

    async def _prepare(self) -> None:
        self.rels_per_node = await self.diff.get_relationships_per_node()
        node_ids = await self.diff.get_node_id_per_kind()

        self.display_labels = await get_display_labels(nodes=node_ids, db=self.db)

    def _add_node_to_diff(self, node_id: str, kind: str) -> None:
        if node_id not in self.entries:
            self.entries[node_id] = BranchDiffEntry(id=node_id, kind=kind, path=f"data/{node_id}")

    def _add_node_element_attribute(
        self,
        branch_diff_node: BranchDiffNode,
        element: BranchDiffAttribute,
    ) -> None:
        node_id = branch_diff_node.id
        branch = branch_diff_node.branch
        if element.name not in self.entries[node_id].elements:
            self.entries[node_id].elements[element.name] = BranchDiffElement(
                type=element.type,
                name=element.name,
                path=f"data/{node_id}/{element.name}",
                change=BranchDiffElementAttribute(id=element.id, action=element.action),
            )

        diff_element: BranchDiffElement = self.entries[node_id].elements[element.name]
        change = diff_element.change
        if not isinstance(change, BranchDiffElementAttribute):
            return

        branch_diff_node_element = branch_diff_node.elements.get(element.name)
        change.branches.append(branch)
        if element.value:
            if not change.value:
                change.value = BranchDiffPropertyCollection(path=f"data/{node_id}/{element.name}/value")
            change.value.changes.append(
                BranchDiffProperty(
                    branch=branch,
                    type=element.value.type,
                    changed_at=element.value.changed_at,
                    action=element.value.action,
                    value=element.value.value,
                )
            )
            change.summary.inc(element.value.action.value)
            if branch_diff_node_element:
                branch_diff_node_element.summary.inc(element.value.action.value)

        for prop in element.properties:
            if prop.type not in change.properties:
                change.properties[prop.type] = BranchDiffPropertyCollection(
                    path=f"data/{node_id}/{element.name}/property/{prop.type}"
                )
            change.properties[prop.type].changes.append(prop)
            change.summary.inc(prop.action.value)
            if branch_diff_node_element and element.value:
                branch_diff_node_element.summary.inc(element.value.action.value)

    def _add_node_element_relationship(
        self,
        branch_diff_node: BranchDiffNode,
        element_name: str,
        relationship: Union[BranchDiffRelationshipOne, BranchDiffRelationshipMany],
    ) -> None:
        if isinstance(relationship, BranchDiffRelationshipOne):
            self._add_node_element_relationship_one(
                branch_diff_node=branch_diff_node, element_name=element_name, relationship=relationship
            )
            return

        self._add_node_element_relationship_many(
            branch_diff_node=branch_diff_node, element_name=element_name, relationship=relationship
        )

    def _add_node_element_relationship_one(
        self,
        branch_diff_node: BranchDiffNode,
        element_name: str,
        relationship: BranchDiffRelationshipOne,
    ) -> None:
        node_id = branch_diff_node.id
        branch = branch_diff_node.branch
        if element_name not in self.entries[node_id].elements:
            self.entries[node_id].elements[element_name] = BranchDiffElement(
                type=DiffElementType.RELATIONSHIP_ONE,
                name=element_name,
                path=f"data/{node_id}/{element_name}",
                change=BranchDiffElementRelationshipOne(id=relationship.id, identifier=relationship.identifier),
            )

        diff_element = self.entries[node_id].elements[element_name]
        change = diff_element.change
        if not isinstance(change, BranchDiffElementRelationshipOne):
            return

        branch_diff_node_element = branch_diff_node.elements.get(element_name)
        if branch not in change.branches:
            change.branches.append(branch)

        change.action[branch] = relationship.action

        if relationship.peer.new or relationship.peer.previous:
            if not change.peer:
                change.peer = BranchDiffRelationshipOnePeerCollection(path=f"data/{node_id}/{element_name}/peer")

            change.peer.add_change(
                BranchDiffRelationshipOnePeer(
                    branch=branch, new=relationship.peer.new, previous=relationship.peer.previous
                )
            )

        for prop in relationship.properties:
            if prop.type not in change.properties:
                change.properties[prop.type] = BranchDiffPropertyCollection(
                    path=f"data/{node_id}/{element_name}/property/{prop.type}"
                )
            if change.properties[prop.type].add_change(prop):
                change.summary.inc(prop.action.value)
                if branch_diff_node_element:
                    branch_diff_node_element.summary.inc(prop.action.value)

        # Fix: Add summary to element

    def _add_node_element_relationship_many(
        self,
        branch_diff_node: BranchDiffNode,
        element_name: str,
        relationship: BranchDiffRelationshipMany,
    ) -> None:
        node_id = branch_diff_node.id
        branch = branch_diff_node.branch
        if element_name not in self.entries[node_id].elements:
            self.entries[node_id].elements[element_name] = BranchDiffElement(
                type=DiffElementType.RELATIONSHIP_MANY,
                name=element_name,
                path=f"data/{node_id}/{element_name}",
                change=BranchDiffElementRelationshipMany(),
            )

        diff_element = self.entries[node_id].elements[element_name]
        change = diff_element.change
        if not isinstance(change, BranchDiffElementRelationshipMany):
            return

        branch_diff_node_element = branch_diff_node.elements.get(element_name)
        if branch not in change.branches:
            change.branches.add(branch)

        for peer in relationship.peers:
            if not change.identifier:
                change.identifier = peer.identifier

            # Update Action, Branches and Summary
            change.branches.add(peer.branch)
            self.entries[node_id].summary.inc(peer.action.value)
            if branch_diff_node_element:
                branch_diff_node_element.summary.inc(peer.action.value)

            if peer.peer.id not in change.peers:
                change.peers[peer.peer.id] = BranchDiffElementRelationshipManyPeer(
                    peer=peer.peer,
                    path=f"data/{node_id}/{element_name}/{peer.peer.id}",
                )

            peer_element = change.peers[peer.peer.id]

            peer_element.branches.add(peer.branch)
            peer_element.action[peer.branch] = peer.action

            for prop in peer.properties:
                if prop.type not in peer_element.properties:
                    peer_element.properties[prop.type] = BranchDiffPropertyCollection(
                        path=f"data/{node_id}/{element_name}/{peer.peer.id}/property/{prop.type}"
                    )
                peer_element.properties[prop.type].changes.append(prop)
                change.summary.inc(prop.action.value)
                if branch_diff_node_element:
                    branch_diff_node_element.summary.inc(prop.action.value)

    async def _process_nodes(self) -> None:
        # Generate the Diff per node and associated the appropriate relationships if they are present in the schema
        for branch_name, items in self.nodes.items():
            for item in items.values():
                if self.kinds_to_include and item.kind not in self.kinds_to_include:
                    continue

                branch_diff_node = await self._process_one_node(node_diff=item, branch_name=branch_name)

                self.diffs.append(branch_diff_node)

    async def _process_one_node(self, node_diff: NodeDiffElement, branch_name: str) -> BranchDiffNode:
        node_diff_graphql = node_diff.to_graphql()

        # We need to convert the list of attributes to a dict under elements
        node_diff_dict = copy.deepcopy(node_diff_graphql)
        del node_diff_dict["attributes"]
        node_diff_dict["branch"] = branch_name
        node_diff_elements = {attr["name"]: attr for attr in node_diff_graphql["attributes"]}

        display_label = self._get_node_display_label(branch_name=branch_name, node_id=node_diff.id)
        branch_diff_node = BranchDiffNode(**node_diff_dict, elements=node_diff_elements, display_label=display_label)
        self._add_node_to_diff(node_id=node_diff_dict["id"], kind=node_diff_dict["kind"])
        self._set_display_label(node_id=node_diff_dict["id"], branch=branch_name, display_label=display_label)
        self._set_node_action(node_id=node_diff_dict["id"], branch=branch_name, action=node_diff_dict["action"])
        schema = registry.schema.get(name=node_diff.kind, branch=node_diff.branch)

        # Extract the value from the list of properties
        for element in branch_diff_node.elements.values():
            if not isinstance(element, BranchDiffAttribute):
                continue
            self._add_node_summary(branch_diff_node=branch_diff_node, action=element.action)

            for prop in element.properties:
                if prop.type == "HAS_VALUE":
                    element.value = prop
                else:
                    element.summary.inc(prop.action.value)

            if element.value:
                element.properties.remove(element.value)
            self._add_node_element_attribute(branch_diff_node=branch_diff_node, element=element)

        if branch_diff_node.id not in self.rels_per_node[branch_name]:
            return branch_diff_node

        branch_display_label_map = self._get_branch_display_label_map(branch_name)
        for rel_name, rels in self.rels_per_node[branch_name][branch_diff_node.id].items():
            rel_schema = schema.get_relationship_by_identifier(id=rel_name, raise_on_error=False)
            if not rel_schema:
                continue
            diff_rel: Optional[Union[BranchDiffRelationshipOne, BranchDiffRelationshipMany]] = None
            if rel_schema.cardinality == RelationshipCardinality.ONE:
                diff_rel = extract_diff_relationship_one(
                    node_id=branch_diff_node.id,
                    name=rel_schema.name,
                    identifier=rel_name,
                    rels=rels,
                    display_labels=branch_display_label_map,
                )
            elif rel_schema.cardinality == RelationshipCardinality.MANY:
                diff_rel = extract_diff_relationship_many(
                    node_id=branch_diff_node.id,
                    name=rel_schema.name,
                    identifier=rel_name,
                    rels=rels,
                    display_labels=branch_display_label_map,
                )

            if not diff_rel:
                continue
            branch_diff_node.elements[diff_rel.name] = diff_rel
            self._add_node_summary(branch_diff_node=branch_diff_node, action=diff_rel.action)
            self._add_node_element_relationship(
                branch_diff_node=branch_diff_node,
                element_name=diff_rel.name,
                relationship=diff_rel,
            )
        return branch_diff_node

    async def _process_relationships(self) -> None:
        # Check if all nodes associated with a relationship have been accounted for
        # If a node is missing it means its changes are only related to its relationships
        for branch_name, _ in self.rels_per_node.items():
            for node_in_rel_id, relationship_diffs_by_name in self.rels_per_node[branch_name].items():
                if node_in_rel_id in self.entries:
                    continue

                branch_diff_node = await self._process_one_node_relationships(
                    node_id=node_in_rel_id,
                    relationship_diffs_by_name=relationship_diffs_by_name,
                    branch_name=branch_name,
                )

                if branch_diff_node:
                    self.diffs.append(branch_diff_node)

    async def _process_one_node_relationships(
        self, node_id: str, relationship_diffs_by_name: Dict[str, List[RelationshipDiffElement]], branch_name: str
    ) -> Optional[BranchDiffNode]:
        node_diff = None
        node_display_label = self._get_node_display_label(branch_name=branch_name, node_id=node_id)
        branch_display_label_map = self._get_branch_display_label_map(branch_name)
        for rel_name, rels in relationship_diffs_by_name.items():
            node_kind = rels[0].nodes[node_id].kind

            if self.kinds_to_include and node_kind not in self.kinds_to_include:
                continue

            schema = registry.schema.get(name=node_kind, branch=branch_name)
            rel_schema = schema.get_relationship_by_identifier(id=rel_name, raise_on_error=False)
            if not rel_schema:
                continue

            if not node_diff:
                node_diff = BranchDiffNode(
                    branch=branch_name,
                    id=node_id,
                    kind=node_kind,
                    action=DiffAction.UPDATED,
                    display_label=node_display_label,
                )
            self._add_node_to_diff(node_id=node_id, kind=node_kind)
            self._set_display_label(
                node_id=node_id,
                branch=branch_name,
                display_label=node_display_label,
            )
            self._set_node_action(node_id=node_id, branch=branch_name, action=DiffAction.UPDATED)

            diff_rel: Optional[Union[BranchDiffRelationshipOne, BranchDiffRelationshipMany]] = None
            if rel_schema.cardinality == RelationshipCardinality.ONE:
                diff_rel = extract_diff_relationship_one(
                    node_id=node_id,
                    name=rel_schema.name,
                    identifier=rel_name,
                    rels=rels,
                    display_labels=branch_display_label_map,
                )

            elif rel_schema.cardinality == RelationshipCardinality.MANY:
                diff_rel = extract_diff_relationship_many(
                    node_id=node_id,
                    name=rel_schema.name,
                    identifier=rel_name,
                    rels=rels,
                    display_labels=branch_display_label_map,
                )

            if not diff_rel:
                continue

            node_diff.elements[diff_rel.name] = diff_rel
            self._add_node_summary(branch_diff_node=node_diff, action=diff_rel.action)
            self._add_node_element_relationship(
                branch_diff_node=node_diff,
                element_name=diff_rel.name,
                relationship=diff_rel,
            )
        return node_diff

    async def _parse_diff(self) -> None:
        # Query the Diff per Nodes and per Relationships from the database

        self.nodes = await self.diff.get_nodes()
        self.rels = await self.diff.get_relationships()

        await self._prepare()
        # Organize the Relationships data per node and per relationship name in order to simplify the association with the nodes Later on.

        await self._process_nodes()
        await self._process_relationships()
        self.is_parsed = True

    async def get_branch_diff(self) -> BranchDiff:
        if not self.is_parsed:
            await self._parse_diff()
        return BranchDiff(diffs=list(self.entries.values()))

    async def get_node_diffs_by_branch(self) -> Dict[str, List[BranchDiffNode]]:
        if not self.is_parsed:
            await self._parse_diff()
        node_diffs_by_branch: Dict[str, List[BranchDiffNode]] = defaultdict(list)
        for node_diff in self.diffs:
            node_diffs_by_branch[node_diff.branch].append(node_diff)
        return node_diffs_by_branch

    async def get_summarized_node_diffs(self) -> List[EnrichedDiffSummaryElement]:
        if not self.is_parsed:
            await self._parse_diff()
        enriched_summaries: List[EnrichedDiffSummaryElement] = []
        summaries_by_branch_and_id = await self.diff.get_summaries_by_branch_and_id()

        for node_diff in self.diffs:
            summary = summaries_by_branch_and_id.get(node_diff.branch, {}).get(node_diff.id)
            enriched_summaries.append(
                EnrichedDiffSummaryElement(
                    branch=node_diff.branch,
                    node=node_diff.id,
                    kind=node_diff.kind,
                    actions=summary.actions if summary else [node_diff.action],
                    action=node_diff.action,
                    display_label=node_diff.display_label,
                    elements=node_diff.elements,
                )
            )
        return enriched_summaries


def extract_diff_relationship_one(
    node_id: str, name: str, identifier: str, rels: List[RelationshipDiffElement], display_labels: Dict[str, str]
) -> Optional[BranchDiffRelationshipOne]:
    """Extract a BranchDiffRelationshipOne object from a list of RelationshipDiffElement."""

    changed_at = None

    if len(rels) == 1:
        rel = rels[0]

        if rel.changed_at:
            changed_at = rel.changed_at.to_string()

        peer_list = [rel_node for rel_node in rel.nodes.values() if rel_node.id != node_id]
        if not peer_list:
            log.warning(
                f"extract_diff_relationship_one: unable to find the peer associated with the node {node_id}, Name: {name}"
            )
            return None

        peer = dict(peer_list[0])
        peer["display_label"] = display_labels.get(peer.get("id", None), "")

        if rel.action.value == "added":
            peer_value = {"new": peer}
        else:
            peer_value = {"previous": peer}

        return BranchDiffRelationshipOne(
            branch=rel.branch,
            id=rel.id,
            name=name,
            identifier=identifier,
            peer=BranchDiffRelationshipOnePeerValue.model_validate(peer_value),
            properties=[BranchDiffProperty(**prop.to_graphql()) for prop in rel.properties.values()],
            changed_at=changed_at,
            action=rel.action,
        )

    if len(rels) == 2:
        rel_added = [rel for rel in rels if rel.action.value == "added"][0]
        rel_removed = [rel for rel in rels if rel.action.value == "removed"][0]

        peer_added = dict([rel_node for rel_node in rel_added.nodes.values() if rel_node.id != node_id][0])
        peer_added["display_label"] = display_labels.get(peer_added.get("id", None), "")

        peer_removed = dict([rel_node for rel_node in rel_removed.nodes.values() if rel_node.id != node_id][0])
        peer_removed["display_label"] = display_labels.get(peer_removed.get("id", None), "")
        peer_value = {"new": dict(peer_added), "previous": dict(peer_removed)}

        return BranchDiffRelationshipOne(
            branch=rel_added.branch,
            id=rel_added.id,
            name=name,
            identifier=identifier,
            peer=BranchDiffRelationshipOnePeerValue.model_validate(peer_value),
            properties=[BranchDiffProperty(**prop.to_graphql()) for prop in rel_added.properties.values()],
            changed_at=changed_at,
            action=DiffAction.UPDATED,
        )

    if len(rels) > 2:
        log.warning(
            f"extract_diff_relationship_one: More than 2 relationships received, need to investigate. Node ID {node_id}, Name: {name}"
        )

    return None


def extract_diff_relationship_many(
    node_id: str, name: str, identifier: str, rels: List[RelationshipDiffElement], display_labels: Dict[str, str]
) -> Optional[BranchDiffRelationshipMany]:
    """Extract a BranchDiffRelationshipMany object from a list of RelationshipDiffElement."""

    if not rels:
        return None

    rel_diff = BranchDiffRelationshipMany(
        branch=rels[0].branch,
        name=name,
        identifier=identifier,
    )

    for rel in rels:
        changed_at = None
        if rel.changed_at:
            changed_at = rel.changed_at.to_string()

        peer = [rel_node for rel_node in rel.nodes.values() if rel_node.id != node_id][0].model_dump(
            exclude={"db_id", "labels"}
        )
        peer["display_label"] = display_labels.get(peer["id"], "")

        rel_diff.summary.inc(rel.action.value)

        rel_diff.peers.append(
            BranchDiffRelationshipManyElement(
                branch=rel.branch,
                id=rel.id,
                identifier=identifier,
                peer=BranchDiffRelationshipPeerNode(**peer),
                properties=[BranchDiffProperty(**prop.to_graphql()) for prop in rel.properties.values()],
                changed_at=changed_at,
                action=rel.action,
            )
        )

    return rel_diff
