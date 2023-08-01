import copy
import enum
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Request
from fastapi.logger import logger
from neo4j import AsyncSession
from pydantic import BaseModel, Field

from infrahub.api.dependencies import get_branch_dep, get_current_user, get_session
from infrahub.core import get_branch, registry
from infrahub.core.branch import Branch, Diff, RelationshipDiffElement
from infrahub.core.constants import DiffAction
from infrahub.core.manager import NodeManager
from infrahub.core.schema_manager import INTERNAL_SCHEMA_NODE_KINDS

if TYPE_CHECKING:
    from infrahub.message_bus.rpc import InfrahubRpcClient

# pylint    : disable=too-many-branches

router = APIRouter(prefix="/diff")


class DiffElementType(str, enum.Enum):
    ATTRIBUTE = "Attribute"
    RELATIONSHIP_ONE = "RelationshipOne"
    RELATIONSHIP_MANY = "RelationshipMany"


class DiffSummary(BaseModel):
    added: int = 0
    removed: int = 0
    updated: int = 0

    def inc(self, name: str) -> int:
        """Increase one of the counter by 1.

        Return the new value of the counter.
        """
        try:
            cnt = getattr(self, name)
        except AttributeError as exc:
            raise ValueError(f"{name} is not a valid counter in DiffSummary.") from exc

        new_value = cnt + 1
        setattr(self, name, new_value)

        return new_value


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


class BranchDiffRelationshipManyElement(BaseModel):
    branch: str
    id: str
    identifier: str
    summary: DiffSummary = DiffSummary()
    peer: BranchDiffRelationshipPeerNode
    properties: List[BranchDiffProperty] = Field(default_factory=list)
    changed_at: Optional[str]
    action: DiffAction


class BranchDiffRelationshipMany(BaseModel):
    type: DiffElementType = DiffElementType.RELATIONSHIP_MANY
    branch: str
    identifier: str
    summary: DiffSummary = DiffSummary()
    name: str
    peers: List[BranchDiffRelationshipManyElement] = Field(default_factory=list)

    @property
    def action(self) -> DiffAction:
        if self.summary.added and not self.summary.updated and not self.summary.removed:
            return DiffAction.ADDED
        if not self.summary.added and not self.summary.updated and self.summary.removed:
            return DiffAction.REMOVED
        return DiffAction.UPDATED


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
    display_name: Optional[str] = None
    commit_from: str
    commit_to: str
    files: List[BranchDiffFile] = Field(default_factory=list)


class BranchDiffArtifactStorage(BaseModel):
    storage_id: str
    checksum: str


class BranchDiffArtifact(BaseModel):
    branch: str
    id: str
    display_label: Optional[str] = None
    action: DiffAction
    item_new: Optional[BranchDiffArtifactStorage] = None
    item_previous: Optional[BranchDiffArtifactStorage] = None


async def get_display_labels_per_kind(kind: str, ids: List[str], branch_name: str, session: AsyncSession):
    """Return the display_labels of a list of nodes of a specific kind."""
    branch = await get_branch(branch=branch_name, session=session)
    schema = registry.get_schema(name=kind, branch=branch)
    fields = schema.generate_fields_for_display_label()
    nodes = await NodeManager.get_many(ids=ids, fields=fields, session=session, branch=branch)
    return {node_id: await node.render_display_label(session=session) for node_id, node in nodes.items()}


async def get_display_labels(nodes: Dict[str, Dict[str, List[str]]], session: AsyncSession) -> Dict[str, str]:
    """Query the display_labels of a group of nodes organized per branch and per kind."""
    response: Dict[str, str] = {}
    for branch_name, items in nodes.items():
        for kind, ids in items.items():
            labels = await get_display_labels_per_kind(kind=kind, ids=ids, session=session, branch_name=branch_name)
            response.update(labels)

    return response


def extract_diff_relationship_one(  # pylint: disable=too-many-return-statements
    node_id: str, name: str, identifier: str, rels: List[RelationshipDiffElement], display_labels: Dict[str, str]
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

        peer_list = [rel_node for rel_node in rel.nodes.values() if rel_node.id != node_id]
        if not peer_list:
            logger.warning(
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
            peer=peer_value,
            properties=[prop.to_graphql() for prop in rel_added.properties.values()],
            changed_at=changed_at,
            action="updated",
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

        peer = [rel_node for rel_node in rel.nodes.values() if rel_node.id != node_id][0].dict(
            exclude={"db_id", "labels"}
        )
        peer["display_label"] = display_labels.get(peer["id"], "")

        rel_diff.summary.inc(rel.action.value)

        rel_diff.peers.append(
            BranchDiffRelationshipManyElement(
                branch=rel.branch,
                id=rel.id,
                identifier=identifier,
                peer=peer,
                properties=[prop.to_graphql() for prop in rel.properties.values()],
                changed_at=changed_at,
                action=rel.action,
            )
        )

    return rel_diff


async def generate_diff_payload(  # pylint: disable=too-many-branches,too-many-statements
    session: AsyncSession, diff: Diff, kinds_to_include: Optional[List[str]] = None
) -> Dict[str, List[BranchDiffNode]]:
    response = defaultdict(list)
    nodes_in_diff = []

    # Query the Diff per Nodes and per Relationships from the database
    nodes = await diff.get_nodes(session=session)
    rels = await diff.get_relationships(session=session)

    # Organize the Relationships data per node and per relationship name in order to simplify the association with the nodes Later on.
    rels_per_node = await diff.get_relationships_per_node(session=session)
    node_ids = await diff.get_node_id_per_kind(session=session)

    display_labels = await get_display_labels(nodes=node_ids, session=session)

    # Generate the Diff per node and associated the appropriate relationships if they are present in the schema
    for branch_name, items in nodes.items():  # pylint: disable=too-many-nested-blocks
        for item in items.values():
            if kinds_to_include and item.kind not in kinds_to_include:
                continue

            item_graphql = item.to_graphql()

            # We need to convert the list of attributes to a dict under elements
            item_dict = copy.deepcopy(item_graphql)
            del item_dict["attributes"]
            item_elements = {attr["name"]: attr for attr in item_graphql["attributes"]}

            node_diff = BranchDiffNode(
                **item_dict, elements=item_elements, display_label=display_labels.get(item.id, "")
            )

            schema = registry.get_schema(name=node_diff.kind, branch=node_diff.branch)

            # Extract the value from the list of properties
            for _, element in node_diff.elements.items():
                node_diff.summary.inc(element.action.value)

                for prop in element.properties:
                    if prop.type == "HAS_VALUE":
                        element.value = prop
                    else:
                        element.summary.inc(prop.action.value)

                if element.value:
                    element.properties.remove(element.value)

            if item.id in rels_per_node[branch_name]:
                for rel_name, rels in rels_per_node[branch_name][item.id].items():
                    if rel_schema := schema.get_relationship_by_identifier(id=rel_name, raise_on_error=False):
                        diff_rel = None
                        if rel_schema.cardinality == "one":
                            diff_rel = extract_diff_relationship_one(
                                node_id=item.id,
                                name=rel_schema.name,
                                identifier=rel_name,
                                rels=rels,
                                display_labels=display_labels,
                            )
                        elif rel_schema.cardinality == "many":
                            diff_rel = extract_diff_relationship_many(
                                node_id=item.id,
                                name=rel_schema.name,
                                identifier=rel_name,
                                rels=rels,
                                display_labels=display_labels,
                            )

                        if diff_rel:
                            node_diff.elements[diff_rel.name] = diff_rel
                            node_diff.summary.inc(diff_rel.action.value)

            response[branch_name].append(node_diff)
            nodes_in_diff.append(node_diff.id)

    # Check if all nodes associated with a relationship have been accounted for
    # If a node is missing it means its changes are only related to its relationships
    for branch_name, _ in rels_per_node.items():
        for node_in_rel, _ in rels_per_node[branch_name].items():
            if node_in_rel in nodes_in_diff:
                continue

            node_diff = None
            for rel_name, rels in rels_per_node[branch_name][node_in_rel].items():
                node_kind = rels[0].nodes[node_in_rel].kind

                if kinds_to_include and node_kind not in kinds_to_include:
                    continue

                schema = registry.get_schema(name=node_kind, branch=branch_name)
                rel_schema = schema.get_relationship_by_identifier(id=rel_name, raise_on_error=False)
                if not rel_schema:
                    continue

                if not node_diff:
                    node_diff = BranchDiffNode(
                        branch=branch_name,
                        id=node_in_rel,
                        kind=node_kind,
                        action=DiffAction.UPDATED,
                        display_label=display_labels.get(node_in_rel, ""),
                    )

                if rel_schema.cardinality == "one":
                    diff_rel = extract_diff_relationship_one(
                        node_id=node_in_rel,
                        name=rel_schema.name,
                        identifier=rel_name,
                        rels=rels,
                        display_labels=display_labels,
                    )
                    if diff_rel:
                        node_diff.elements[diff_rel.name] = diff_rel
                        node_diff.summary.inc(diff_rel.action.value)

                elif rel_schema.cardinality == "many":
                    diff_rel = extract_diff_relationship_many(
                        node_id=node_in_rel,
                        name=rel_schema.name,
                        identifier=rel_name,
                        rels=rels,
                        display_labels=display_labels,
                    )
                    if diff_rel:
                        node_diff.elements[diff_rel.name] = diff_rel
                        node_diff.summary.inc(diff_rel.action.value)

            if node_diff:
                response[branch_name].append(node_diff)

    return response


@router.get("/data")
async def get_diff_data(  # pylint: disable=too-many-branches,too-many-statements
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(get_branch_dep),
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
    _: str = Depends(get_current_user),
) -> Dict[str, List[BranchDiffNode]]:
    diff = await branch.diff(session=session, diff_from=time_from, diff_to=time_to, branch_only=branch_only)
    schema = registry.schema.get_full(branch=branch)
    return await generate_diff_payload(diff=diff, session=session, kinds_to_include=list(schema.keys()))


@router.get("/schema")
async def get_diff_schema(  # pylint: disable=too-many-branches,too-many-statements
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(get_branch_dep),
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
    _: str = Depends(get_current_user),
) -> Dict[str, List[BranchDiffNode]]:
    diff = await branch.diff(session=session, diff_from=time_from, diff_to=time_to, branch_only=branch_only)
    return await generate_diff_payload(diff=diff, session=session, kinds_to_include=INTERNAL_SCHEMA_NODE_KINDS)


@router.get("/files")
async def get_diff_files(
    request: Request,
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(get_branch_dep),
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
    _: str = Depends(get_current_user),
) -> Dict[str, Dict[str, BranchDiffRepository]]:
    response: Dict[str, Dict[str, BranchDiffRepository]] = defaultdict(dict)
    rpc_client: InfrahubRpcClient = request.app.state.rpc_client

    # Query the Diff for all files and repository from the database
    diff = await branch.diff(session=session, diff_from=time_from, diff_to=time_to, branch_only=branch_only)
    diff_files = await diff.get_files(session=session, rpc_client=rpc_client)

    for branch_name, items in diff_files.items():
        for item in items:
            if item.repository not in response[branch_name]:
                response[branch_name][item.repository] = BranchDiffRepository(
                    id=item.repository,
                    display_name=f"Repository ({item.repository})",
                    commit_from=item.commit_from,
                    commit_to=item.commit_to,
                    branch=branch_name,
                )

            response[branch_name][item.repository].files.append(BranchDiffFile(**item.to_graphql()))

    return response


@router.get("/artifacts")
async def get_diff_artifacts(
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(get_branch_dep),
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
    _: str = Depends(get_current_user),
) -> Dict[str, BranchDiffArtifact]:
    response = {}

    # Query the Diff for all artifacts
    diff = await branch.diff(session=session, diff_from=time_from, diff_to=time_to, branch_only=branch_only)
    payload = await generate_diff_payload(diff=diff, session=session, kinds_to_include=["CoreArtifact"])

    for branch_name, data in payload.items():
        for node in data:
            if "storage_id" not in node.elements or "checksum" not in node.elements:
                continue

            diff_artifact = BranchDiffArtifact(
                id=node.id, action=node.action, branch=branch_name, display_label=node.display_label
            )

            if node.action in [DiffAction.UPDATED, DiffAction.ADDED]:
                diff_artifact.item_new = BranchDiffArtifactStorage(
                    storage_id=node.elements["storage_id"].value.value.new,
                    checksum=node.elements["checksum"].value.value.new,
                )

            if node.action in [DiffAction.UPDATED, DiffAction.REMOVED]:
                diff_artifact.item_previous = BranchDiffArtifactStorage(
                    storage_id=node.elements["storage_id"].value.value.previous,
                    checksum=node.elements["checksum"].value.value.previous,
                )

            response[node.id] = diff_artifact

    return response
