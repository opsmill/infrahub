import copy
import enum
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Request
from fastapi.logger import logger
from neo4j import AsyncSession
from pydantic import BaseModel, Field

from infrahub.api.dependencies import get_session
from infrahub.core import get_branch, registry
from infrahub.core.branch import Branch, RelationshipDiffElement
from infrahub.core.constants import DiffAction
from infrahub.core.manager import NodeManager
from infrahub.message_bus.rpc import InfrahubRpcClient

# pylint    : disable=too-many-branches

router = APIRouter(prefix="/dev/diff")


class DiffElementType(enum.Flag):
    ATTRIBUTE = "Attribute"
    RELATIONSHIP_ONE = "RelationshipOne"
    RELATIONSHIP_MANY = "RelationshipMany"


class DiffSummary(BaseModel):
    added: int = 0
    removed: int = 0
    updated: int = 0


class BranchDiffPropertyValue(BaseModel):
    new: Any
    previous: Any


class BranchDiffProperty(BaseModel):
    branch: str
    type: str
    changed_at: Optional[str]
    action: DiffAction
    value: BranchDiffPropertyValue


class BranchDiffAttribute(BaseModel):
    type: DiffElementType = DiffElementType.ATTRIBUTE
    name: str
    id: str
    changed_at: Optional[str]
    summary: DiffSummary = DiffSummary()
    action: DiffAction
    value: Optional[BranchDiffProperty]
    properties: List[BranchDiffProperty]


class BranchDiffRelationshipPeerNode(BaseModel):
    id: str
    kind: str
    display_label: Optional[str]


class BranchDiffRelationshipOnePeerValue(BaseModel):
    new: Optional[BranchDiffRelationshipPeerNode]
    previous: Optional[BranchDiffRelationshipPeerNode]


class BranchDiffRelationshipOne(BaseModel):
    type: DiffElementType = DiffElementType.RELATIONSHIP_ONE
    branch: str
    id: str
    identifier: str
    summary: DiffSummary = DiffSummary()
    name: str
    peer: BranchDiffRelationshipOnePeerValue
    properties: List[BranchDiffProperty] = Field(default_factory=list)
    changed_at: Optional[str]
    action: DiffAction


class BranchDiffRelationshipMany(BaseModel):
    type: DiffElementType = DiffElementType.RELATIONSHIP_MANY
    branch: str
    id: str
    identifier: str
    summary: DiffSummary = DiffSummary()
    name: str
    peer: BranchDiffRelationshipPeerNode
    properties: List[BranchDiffProperty] = Field(default_factory=list)
    changed_at: Optional[str]
    action: DiffAction


class BranchDiffNode(BaseModel):
    branch: str
    kind: str
    id: str
    summary: DiffSummary = DiffSummary()
    display_label: str
    changed_at: Optional[str]
    action: DiffAction
    elements: Dict[str, Union[BranchDiffRelationshipOne, BranchDiffRelationshipMany, BranchDiffAttribute]] = Field(
        default_factory=dict
    )


class BranchDiffFile(BaseModel):
    branch: str
    location: str
    action: DiffAction


class BranchDiffRepository(BaseModel):
    branch: str
    id: str
    display_name: Optional[str]
    files: List[BranchDiffFile] = Field(default_factory=list)


async def get_display_labels_per_kind(kind: str, ids: List[str], branch_name: str, session: AsyncSession):
    """Return the display_labels of a list of nodes of a specific kind."""
    branch = await get_branch(branch=branch_name, session=session)
    schema = registry.get_schema(name=kind, branch=branch)
    fields = schema.generate_fields_for_display_label()
    nodes = await NodeManager.get_many(ids=ids, fields=fields, session=session, branch=branch)
    return {node_id: await node.render_display_label(session=session) for node_id, node in nodes.items()}


async def get_display_labels(nodes: Dict[str, List[str]], session: AsyncSession) -> Dict[str, str]:
    """Query the display_labels of a group of nodes organized per branch and per kind."""
    response: Dict[str, str] = {}
    for branch_name, items in nodes.items():
        for kind, ids in items.items():
            labels = await get_display_labels_per_kind(kind=kind, ids=ids, session=session, branch_name=branch_name)
            response.update(labels)

    return response


def extract_diff_relationship_one(
    node_id: str, name: str, rels: List[RelationshipDiffElement]
) -> Optional[BranchDiffRelationshipOne]:
    """Extract a BranchDiffRelationshipOne object from a list of RelationshipDiffElement."""

    changed_at = None
    if len(rels) > 2:
        logger.warning(
            f"extract_diff_relationship_one: More than 2 relationships received, need to investigate. Node ID {node_id}, Name: {name}"
        )
        return None

    if len(rels) == 0:
        return None

    if len(rels) == 1:
        rel = rels[0]

        if rel.changed_at:
            changed_at = rel.changed_at.to_string()

        peer = [rel_node for rel_node in rel.nodes.values() if rel_node.id != node_id][0]

        if rel.action.value == "added":
            peer_value = {"new": dict(peer)}
        else:
            peer_value = {"previous": dict(peer)}

        return BranchDiffRelationshipOne(
            branch=rel.branch,
            id=rel.id,
            name=name,
            identifier=rel.name,
            peer=peer_value,
            properties=[prop.to_graphql() for prop in rel.properties.values()],
            changed_at=changed_at,
            action=rel.action,
        )

    if len(rels) == 2:
        actions = [rel.action.value for rel in rels]
        if sorted(actions) != ["added", "removed"]:
            logger.warning(
                f"extract_diff_relationship_one: 2 relationships with actions {actions} received, need to investigate: Node ID {node_id}, Name: {name}"
            )
            return None

        rel_added = [rel for rel in rels if rel.action.value == "added"]
        rel_removed = [rel for rel in rels if rel.action.value == "removed"]

        peer_added = [rel_node for rel_node in rel_added.nodes.values() if rel_node.id != node_id][0]
        peer_removed = [rel_node for rel_node in rel_removed.nodes.values() if rel_node.id != node_id][0]

        if peer_added.changed_at:
            changed_at = peer_added.changed_at.to_string()
        elif peer_removed.changed_at:
            changed_at = peer_removed.changed_at.to_string()

        peer_value = {"new": dict(peer_added), "previous": dict(peer_removed)}

        return BranchDiffRelationshipOne(
            branch=rel_added.branch,
            id=rel_added.id,
            name=name,
            identifier=rel_added.name,
            peer=peer_value,
            properties=[prop.to_graphql() for prop in rel_added.properties.values()],
            changed_at=changed_at,
            action=rel_added.action,
        )


@router.get("/data")
async def get_diff_data(  # pylint: disable=too-many-branches
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
) -> Dict[str, List[BranchDiffNode]]:
    branch: Branch = await get_branch(session=session, branch=branch)

    response = defaultdict(list)
    nodes_in_diff = []

    # Query the Diff per Nodes and per Relationships from the database
    diff = await branch.diff(session=session, diff_from=time_from, diff_to=time_to, branch_only=branch_only)
    nodes = await diff.get_nodes(session=session)
    rels = await diff.get_relationships(session=session)

    # Node IDs organized per Branch and per Kind
    node_ids = defaultdict(lambda: defaultdict(list))

    # Organize the Relationships data per node and per relationship name in order to simplify the association with the nodes Later on.
    rels_per_node: Dict[str, Dict[str, List[RelationshipDiffElement]]] = defaultdict(lambda: defaultdict(list))
    for branch_name, items in rels.items():
        for item in items.values():
            for sub_item in item.values():
                for node_id, node in sub_item.nodes.items():
                    rels_per_node[node_id][sub_item.name].append(sub_item)
                    if node_id not in node_ids[branch_name][node.kind]:
                        node_ids[branch_name][node.kind].append(node_id)

    # Extract the id of all nodes ahead of time in order to query all display labels
    for branch_name, items in nodes.items():
        for item in items.values():
            if item.id not in node_ids[branch_name][item.kind]:
                node_ids[branch_name][item.kind].append(item.id)

    display_labels = await get_display_labels(nodes=node_ids, session=session)

    # Generate the Diff per node and associated the appropriate relationships if they are present in the schema
    for branch_name, items in nodes.items():
        for item in items.values():
            item_graphql = item.to_graphql()

            # We need to convert the list of attributes to a dict under elements
            item_dict = copy.deepcopy(item_graphql)
            del item_dict["attributes"]
            item_elements = {attr["name"]: attr for attr in item_graphql["attributes"]}

            node_diff = BranchDiffNode(
                **item_dict, elements=item_elements, display_label=display_labels.get(item.id, "")
            )

            # Extract the value from the list of properties
            for name, element in node_diff.elements.items():
                idx_to_remove = None

                cnt = getattr(node_diff.summary, element.action.value)
                setattr(node_diff.summary, element.action.value, cnt + 1)

                for idx, prop in enumerate(element.properties):
                    if prop.type == "HAS_VALUE":
                        idx_to_remove = idx
                        element.value = prop
                    else:
                        cnt = getattr(element.summary, prop.action.value)
                        setattr(element.summary, prop.action.value, cnt + 1)

                if idx_to_remove:
                    element.properties.pop(idx_to_remove)

            schema = registry.get_schema(name=node_diff.kind, branch=node_diff.branch)

            if item.id in rels_per_node:
                for rel_name, rels in rels_per_node[item.id].items():
                    if rel_schema := schema.get_relationship_by_identifier(id=rel_name, raise_on_error=False):
                        if rel_schema.cardinality == "one":
                            diff_rel = extract_diff_relationship_one(node_id=item.id, name=rel_schema.name, rels=rels)
                            if diff_rel:
                                # diff_rel.peer.display_label = display_labels.get(diff_rel.peer.id, "")
                                node_diff.elements[diff_rel.name] = diff_rel

            response[branch_name].append(node_diff)
            nodes_in_diff.append(node_diff.id)

    # # Check if all nodes associated with a relationship have been accounted for
    # # If a node is missing it means its changes are only related to its relationships
    # for node_in_rel, rels in rels_per_node.items():
    #     if node_in_rel in nodes_in_diff:
    #         continue

    #     node_diff = None
    #     for rel in rels:
    #         schema = registry.get_schema(name=rel.nodes[node_in_rel].kind, branch=rel.branch)
    #         if rel_schema := schema.get_relationship_by_identifier(id=rel.name, raise_on_error=False):
    #             if not node_diff:
    #                 node_diff = BranchDiffNode(
    #                     branch=rel.branch,
    #                     id=node_in_rel,
    #                     kind=rel.nodes[node_in_rel].kind,
    #                     action=DiffAction.UPDATED,
    #                     display_label=display_labels.get(node_in_rel, ""),
    #                 )

    #             diff_rel = extract_diff_relationship(node_id=node_in_rel, name=rel_schema.name, rel=rel)
    #             diff_rel.peer.display_label = display_labels.get(diff_rel.peer.id, "")
    #             node_diff.relationships.append(diff_rel)

    # if node_diff:
    #     response[rel.branch].append(node_diff)

    return response


@router.get("/files")
async def get_diff_files(
    request: Request,
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
) -> Dict[str, Dict[str, BranchDiffRepository]]:
    branch: Branch = await get_branch(session=session, branch=branch)

    response = defaultdict(lambda: defaultdict(list))
    rpc_client: InfrahubRpcClient = request.app.state.rpc_client

    # Query the Diff for all files and repository from the database
    diff = await branch.diff(session=session, diff_from=time_from, diff_to=time_to, branch_only=branch_only)
    diff_files = await diff.get_files(session=session, rpc_client=rpc_client)

    for branch_name, items in diff_files.items():
        for item in items:
            if item.repository not in response[branch_name]:
                response[branch_name][item.repository] = BranchDiffRepository(id=item.repository, branch=branch_name)

            response[branch_name][item.repository].files.append(BranchDiffFile(**item.to_graphql()))

    return response
