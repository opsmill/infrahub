from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from neo4j import AsyncSession
from pydantic import BaseModel, Field

from infrahub.api.dependencies import get_session
from infrahub.core import get_branch, registry
from infrahub.core.branch import Branch, RelationshipDiffElement
from infrahub.core.constants import DiffAction
from infrahub.exceptions import BranchNotFound
from infrahub.message_bus.rpc import InfrahubRpcClient

# pylint    : disable=too-many-branches

router = APIRouter(prefix="/diff")


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
    name: str
    id: str
    changed_at: Optional[str]
    action: DiffAction
    properties: List[BranchDiffProperty]


class BranchDiffRelationshipPeerNode(BaseModel):
    id: str
    kind: str
    display_label: Optional[str]


class BranchDiffRelationship(BaseModel):
    branch: str
    id: str
    identifier: str
    name: str
    peer: BranchDiffRelationshipPeerNode
    properties: List[BranchDiffProperty]
    changed_at: Optional[str]
    action: DiffAction


class BranchDiffNode(BaseModel):
    branch: str
    kind: str
    id: str
    changed_at: Optional[str]
    action: DiffAction
    attributes: List[BranchDiffAttribute] = Field(default_factory=list)
    relationships: List[BranchDiffRelationship] = Field(default_factory=list)


class BranchDiffFile(BaseModel):
    branch: str
    location: str
    action: DiffAction


class BranchDiffRepository(BaseModel):
    branch: str
    id: str
    display_name: Optional[str]
    files: List[BranchDiffFile] = Field(default_factory=list)


def extract_diff_relationship(node_id: str, name: str, rel: RelationshipDiffElement) -> BranchDiffRelationship:
    peer = [rel_node for rel_node in rel.nodes.values() if rel_node.id != node_id][0]

    changed_at = None
    if rel.changed_at:
        changed_at = rel.changed_at.to_string()

    return BranchDiffRelationship(
        branch=rel.branch,
        id=rel.id,
        name=name,
        identifier=rel.name,
        peer=dict(peer),
        properties=[prop.to_graphql() for prop in rel.properties.values()],
        changed_at=changed_at,
        action=rel.action,
    )


@router.get("/data")
async def get_diff_data(
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
) -> Dict[str, List[BranchDiffNode]]:
    try:
        branch: Branch = await get_branch(session=session, branch=branch)
    except BranchNotFound as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    response = defaultdict(list)
    nodes_in_diff = []

    # Query the Diff per Nodes and per Relationships from the database
    diff = await branch.diff(session=session, diff_from=time_from, diff_to=time_to, branch_only=branch_only)
    nodes = await diff.get_nodes(session=session)
    rels = await diff.get_relationships(session=session)

    # Organize the Relationships data per node in order to simplify the association with the nodes Later on.
    rels_per_node: Dict[str, List[RelationshipDiffElement]] = defaultdict(list)

    for items in rels.values():
        for item in items.values():
            for sub_item in item.values():
                for node_id in sub_item.nodes.keys():
                    rels_per_node[node_id].append(sub_item)

    # Generate the Diff per node and associated the appropriate relationships if they are present in the schema
    for branch_name, items in nodes.items():
        for item in items.values():
            node_diff = BranchDiffNode(**item.to_graphql())
            schema = registry.get_schema(name=node_diff.kind, branch=node_diff.branch)

            for rel in rels_per_node.get(item.id, []):
                if rel_schema := schema.get_relationship_by_identifier(id=rel.name, raise_on_error=False):
                    node_diff.relationships.append(
                        extract_diff_relationship(node_id=item.id, name=rel_schema.name, rel=rel)
                    )

            response[branch_name].append(node_diff)
            nodes_in_diff.append(node_diff.id)

    # Check if all nodes associated with a relationship have been accounted for
    # If a node is missing it means its changes are only related to its relationships
    for node_in_rel, rels in rels_per_node.items():
        if node_in_rel in nodes_in_diff:
            continue

        node_diff = None
        for rel in rels:
            schema = registry.get_schema(name=rel.nodes[node_in_rel].kind, branch=rel.branch)
            if rel_schema := schema.get_relationship_by_identifier(id=rel.name, raise_on_error=False):
                if not node_diff:
                    node_diff = BranchDiffNode(
                        branch=rel.branch, id=node_in_rel, kind=rel.nodes[node_in_rel].kind, action=DiffAction.UPDATED
                    )

                node_diff.relationships.append(
                    extract_diff_relationship(node_id=node_in_rel, name=rel_schema.name, rel=rel)
                )

        if node_diff:
            response[rel.branch].append(node_diff)

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
    try:
        branch: Branch = await get_branch(session=session, branch=branch)
    except BranchNotFound as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

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
