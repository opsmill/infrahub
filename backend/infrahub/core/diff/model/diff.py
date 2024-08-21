from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field

from infrahub.core.constants import DiffAction, PathType
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp


class RelationshipPath(BaseModel):
    paths: list[str] = Field(default_factory=list)
    conflict_paths: list[str] = Field(default_factory=list)


class BaseDiffElement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def to_graphql(self) -> dict[str, Any]:
        """Recursively Export the model to a dict for GraphQL.
        The main rules of convertion are:
            - Ignore the fields mark as exclude=True
            - Convert the Dict in List
        """
        resp: dict[str, Any] = {}
        for key, value in self:
            field_info = self.model_fields[key]
            if isinstance(value, BaseModel):
                resp[key] = value.to_graphql()  # type: ignore[attr-defined]
            elif isinstance(value, dict):
                resp[key] = [item.to_graphql() for item in value.values()]
            elif field_info.exclude or (field_info.default and getattr(field_info.default, "exclude", False)):
                continue
            elif isinstance(value, Enum):
                resp[key] = value.value
            elif isinstance(value, Timestamp):
                resp[key] = value.to_string()
            elif isinstance(value, Node):
                resp[key] = value.get_id()
            else:
                resp[key] = value

        return resp


class ValueElement(BaseDiffElement):
    previous: Optional[Any] = None
    new: Optional[Any] = None

    def __hash__(self) -> int:
        return hash(type(self))


class PropertyDiffElement(BaseDiffElement):
    branch: str
    type: str
    action: DiffAction
    path: Optional[str] = None
    db_id: str = Field(exclude=True)
    rel_id: str = Field(exclude=True)
    origin_rel_id: Optional[str] = Field(None, exclude=True)
    value: Optional[ValueElement] = None
    changed_at: Optional[Timestamp] = None


class NodeAttributeDiffElement(BaseDiffElement):
    id: str
    name: str
    path: str
    action: DiffAction
    db_id: str = Field(exclude=True)
    rel_id: str = Field(exclude=True)
    origin_rel_id: Optional[str] = Field(None, exclude=True)
    changed_at: Optional[Timestamp] = None
    properties: dict[str, PropertyDiffElement]


class NodeDiffElement(BaseDiffElement):
    branch: Optional[str] = None
    labels: list[str]
    kind: str
    id: str
    path: str
    action: DiffAction
    db_id: str = Field(exclude=True)
    rel_id: Optional[str] = Field(None, exclude=True)
    changed_at: Optional[Timestamp] = None
    attributes: dict[str, NodeAttributeDiffElement] = Field(default_factory=dict)


class RelationshipEdgeNodeDiffElement(BaseDiffElement):
    id: str
    db_id: Optional[str] = Field(None, exclude=True)
    rel_id: Optional[str] = Field(None, exclude=True)
    labels: list[str]
    kind: str


class RelationshipDiffElement(BaseDiffElement):
    branch: str
    id: str
    db_id: str = Field(exclude=True)
    name: str
    action: DiffAction
    nodes: dict[str, RelationshipEdgeNodeDiffElement]
    properties: dict[str, PropertyDiffElement]
    changed_at: Optional[Timestamp] = None
    paths: list[str]
    conflict_paths: list[str]

    def get_node_id_by_kind(self, kind: str) -> Optional[str]:
        ids = [rel.id for rel in self.nodes.values() if rel.kind == kind]
        if ids:
            return ids[0]
        return None


class FileDiffElement(BaseDiffElement):
    branch: str
    location: str
    repository: Node
    action: DiffAction
    commit_from: str
    commit_to: str

    def __hash__(self) -> int:
        return hash((type(self),) + tuple(self.__dict__.values()))


class DiffSummaryElement(BaseModel):
    branch: str = Field(..., description="The branch where the change occurred")
    node: str = Field(..., description="The unique ID of the node")
    kind: str = Field(..., description="The kind of the node as defined by its namespace and name")
    actions: list[DiffAction] = Field(..., description="A list of all actions on this node.")

    def to_graphql(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "node": self.node,
            "kind": self.kind,
            "actions": [action.value for action in self.actions],
        }


class EnrichedDiffSummaryElement(BaseModel):
    branch: str = Field(..., description="The branch where the change occurred")
    node: str = Field(..., description="The unique ID of the node")
    kind: str = Field(..., description="The kind of the node as defined by its namespace and name")
    action: DiffAction
    display_label: str
    elements: dict[str, Union[BranchDiffRelationshipOne, BranchDiffRelationshipMany, BranchDiffAttribute]] = Field(
        default_factory=dict
    )

    @computed_field
    def id(self) -> str:
        return self.node


class ModifiedPath(BaseModel):
    type: ModifiedPathType
    node_id: str
    path_type: PathType
    kind: str
    element_name: Optional[str] = None
    property_name: Optional[str] = None
    peer_id: Optional[str] = None
    action: DiffAction
    change: Optional[ValueElement] = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModifiedPath):
            raise NotImplementedError

        if self.modification_type != other.modification_type:
            return False

        if self.modification_type == "node":
            if self.action == other.action and self.action in [DiffAction.REMOVED, DiffAction.UPDATED]:
                return False

        if self.modification_type == "element":
            if self.action == other.action and self.action == DiffAction.REMOVED:
                return False

        return self.type == other.type and self.node_id == other.node_id

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ModifiedPath):
            raise NotImplementedError
        return str(self) < str(other)

    def __hash__(self) -> int:
        return hash((type(self),) + tuple(self.__dict__.values()))

    def _path(self, with_peer: bool = True) -> str:
        identifier = f"{self.type.value}/{self.node_id}"
        if self.element_name:
            identifier += f"/{self.element_name}"

        if self.path_type == PathType.RELATIONSHIP_ONE and not self.property_name:
            identifier += "/peer"

        if with_peer and self.peer_id:
            identifier += f"/{self.peer_id}"

        if self.property_name and self.property_name == "HAS_VALUE":
            identifier += "/value"
        elif self.property_name:
            identifier += f"/property/{self.property_name}"

        return identifier

    def __str__(self) -> str:
        return self._path()

    @property
    def change_type(self) -> str:
        if self.path_type in [PathType.ATTRIBUTE, PathType.RELATIONSHIP_MANY, PathType.RELATIONSHIP_ONE]:
            if self.property_name and self.property_name != "HAS_VALUE":
                return f"{self.path_type.value}_property"
            return f"{self.path_type.value}_value"
        return self.path_type.value

    @property
    def conflict_path(self) -> str:
        return self._path(with_peer=False)

    @property
    def modification_type(self) -> str:
        if self.element_name:
            return "element"

        return "node"


class BranchChanges(ValueElement):
    branch: str
    action: DiffAction

    def __hash__(self) -> int:
        return hash(str(self.previous) + str(self.new) + str(self.branch) + str(self.action.value))


class ObjectConflict(BaseModel):
    name: str
    type: str
    kind: str
    id: str
    conflict_id: str | None = None

    @property
    def label(self) -> str:
        return f"{self.name} ({self.id})"

    def to_conflict_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude={"conflict_id"})


class DataConflict(ObjectConflict):
    conflict_path: str
    path: str
    path_type: PathType
    property_name: Optional[str] = None
    change_type: str
    changes: list[BranchChanges] = Field(default_factory=list)

    def to_conflict_dict(self) -> dict[str, Any]:
        conflict_dict = self.model_dump(exclude={"path_type"})
        conflict_dict["path_type"] = self.path_type.value
        return conflict_dict

    def __str__(self) -> str:
        return self.path


class SchemaConflict(ObjectConflict):
    path: str
    branch: str
    value: str

    @property
    def label(self) -> str:
        return self.value


class DiffElementType(str, Enum):
    ATTRIBUTE = "Attribute"
    RELATIONSHIP_ONE = "RelationshipOne"
    RELATIONSHIP_MANY = "RelationshipMany"


class ModifiedPathType(Enum):
    DATA = "data"


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
    new: Any = None
    previous: Any = None


class BranchDiffProperty(BaseModel):
    branch: str
    type: str
    changed_at: Optional[str] = None
    action: DiffAction
    value: BranchDiffPropertyValue


class BranchDiffPropertyCollection(BaseModel):
    path: str
    changes: list[BranchDiffProperty] = Field(default_factory=list)

    def add_change(self, change: BranchDiffProperty) -> bool:
        current_branches = [item.branch for item in self.changes]
        if change.branch not in current_branches:
            self.changes.append(change)
            return True

        return False


class BranchDiffAttribute(BaseModel):
    type: DiffElementType = DiffElementType.ATTRIBUTE
    name: str
    id: str
    changed_at: Optional[str] = None
    summary: DiffSummary = Field(default_factory=DiffSummary)
    action: DiffAction
    value: Optional[BranchDiffProperty] = None
    properties: list[BranchDiffProperty] = Field(default_factory=list)


class BranchDiffRelationshipPeerNode(BaseModel):
    id: str
    kind: str
    display_label: Optional[str] = None


# OLD
class BranchDiffRelationshipOnePeerValue(BaseModel):
    new: Optional[BranchDiffRelationshipPeerNode] = None
    previous: Optional[BranchDiffRelationshipPeerNode] = None


# OLD
class BranchDiffRelationshipOne(BaseModel):
    type: DiffElementType = DiffElementType.RELATIONSHIP_ONE
    branch: str
    id: str
    identifier: str
    summary: DiffSummary = Field(default_factory=DiffSummary)
    name: str
    peer: BranchDiffRelationshipOnePeerValue
    properties: list[BranchDiffProperty] = Field(default_factory=list)
    changed_at: Optional[str] = None
    action: DiffAction


# OLD
class BranchDiffRelationshipManyElement(BaseModel):
    branch: str
    id: str
    identifier: str
    summary: DiffSummary = Field(default_factory=DiffSummary)
    peer: BranchDiffRelationshipPeerNode
    properties: list[BranchDiffProperty] = Field(default_factory=list)
    changed_at: Optional[str] = None
    action: DiffAction


# OLD
class BranchDiffRelationshipMany(BaseModel):
    type: DiffElementType = DiffElementType.RELATIONSHIP_MANY
    branch: str
    identifier: str
    summary: DiffSummary = Field(default_factory=DiffSummary)
    name: str
    peers: list[BranchDiffRelationshipManyElement] = Field(default_factory=list)

    @property
    def action(self) -> DiffAction:
        if self.summary.added and not self.summary.updated and not self.summary.removed:
            return DiffAction.ADDED
        if not self.summary.added and not self.summary.updated and self.summary.removed:
            return DiffAction.REMOVED
        return DiffAction.UPDATED


# NEW
class BranchDiffElementAttribute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: DiffElementType = DiffElementType.ATTRIBUTE
    branches: list[str] = Field(default_factory=list)
    id: str = ""
    summary: DiffSummary = Field(default_factory=DiffSummary)
    action: DiffAction = DiffAction.UNCHANGED
    value: Optional[BranchDiffPropertyCollection] = None
    properties: dict[str, BranchDiffPropertyCollection] = Field(default_factory=dict)


# NEW
class BranchDiffRelationshipOnePeer(BaseModel):
    branch: str
    new: Optional[BranchDiffRelationshipPeerNode] = None
    previous: Optional[BranchDiffRelationshipPeerNode] = None


class BranchDiffRelationshipOnePeerCollection(BaseModel):
    path: str
    changes: list[BranchDiffRelationshipOnePeer] = Field(default_factory=list)

    def add_change(self, change: BranchDiffRelationshipOnePeer) -> bool:
        current_branches = [item.branch for item in self.changes]
        if change.branch not in current_branches:
            self.changes.append(change)
            return True

        return False


# NEW
class BranchDiffElementRelationshipOne(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: DiffElementType = DiffElementType.RELATIONSHIP_ONE
    id: str = ""
    identifier: str = ""
    branches: list[str] = Field(default_factory=list)
    summary: DiffSummary = Field(default_factory=DiffSummary)
    peer: Optional[BranchDiffRelationshipOnePeerCollection] = None
    properties: dict[str, BranchDiffPropertyCollection] = Field(default_factory=dict)
    changed_at: Optional[str] = None
    action: dict[str, DiffAction] = Field(default_factory=dict)


class BranchDiffElementRelationshipManyPeer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branches: set[str] = Field(default_factory=set)
    peer: BranchDiffRelationshipPeerNode
    path: str
    properties: dict[str, BranchDiffPropertyCollection] = Field(default_factory=dict)
    changed_at: Optional[str] = None
    action: dict[str, DiffAction] = Field(default_factory=dict)


# NEW
class BranchDiffElementRelationshipMany(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: DiffElementType = DiffElementType.RELATIONSHIP_MANY
    identifier: str = ""
    branches: set[str] = Field(default_factory=set)
    summary: DiffSummary = Field(default_factory=DiffSummary)
    peers: dict[str, BranchDiffElementRelationshipManyPeer] = Field(default_factory=dict)


# NEW
class BranchDiffElement(BaseModel):
    type: DiffElementType
    name: str
    path: str
    change: Union[BranchDiffElementAttribute, BranchDiffElementRelationshipOne, BranchDiffElementRelationshipMany]


# OLD
class BranchDiffNode(BaseModel):
    branch: str
    kind: str
    id: str
    summary: DiffSummary = Field(default_factory=DiffSummary)
    display_label: str
    changed_at: Optional[str] = None
    action: DiffAction
    elements: dict[str, Union[BranchDiffRelationshipOne, BranchDiffRelationshipMany, BranchDiffAttribute]] = Field(
        default_factory=dict
    )


# NEW
class BranchDiffEntry(BaseModel):
    kind: str
    id: str
    path: str
    elements: dict[str, BranchDiffElement] = Field(default_factory=dict)
    summary: DiffSummary = Field(default_factory=DiffSummary)
    action: dict[str, DiffAction] = Field(default_factory=dict)
    display_label: dict[str, str] = Field(default_factory=dict)


#  NEW
class BranchDiff(BaseModel):
    diffs: list[BranchDiffEntry] = Field(default_factory=list)


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
    files: list[BranchDiffFile] = Field(default_factory=list)


class BranchDiffArtifactStorage(BaseModel):
    storage_id: str
    checksum: str


class ArtifactTarget(BaseModel):
    id: str
    kind: str
    display_label: Optional[str] = None


class BranchDiffArtifact(BaseModel):
    branch: str
    id: str
    display_label: Optional[str] = None
    action: DiffAction
    target: Optional[ArtifactTarget] = None
    item_new: Optional[BranchDiffArtifactStorage] = None
    item_previous: Optional[BranchDiffArtifactStorage] = None
