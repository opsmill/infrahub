from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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
    previous: Any | None = None
    new: Any | None = None

    def __hash__(self) -> int:
        return hash(type(self))


class PropertyDiffElement(BaseDiffElement):
    branch: str
    type: str
    action: DiffAction
    path: str | None = None
    db_id: str = Field(exclude=True)
    rel_id: str = Field(exclude=True)
    origin_rel_id: str | None = Field(None, exclude=True)
    value: ValueElement | None = None
    changed_at: Timestamp | None = None


class NodeAttributeDiffElement(BaseDiffElement):
    id: str
    name: str
    path: str
    action: DiffAction
    db_id: str = Field(exclude=True)
    rel_id: str = Field(exclude=True)
    origin_rel_id: str | None = Field(None, exclude=True)
    changed_at: Timestamp | None = None
    properties: dict[str, PropertyDiffElement]


class NodeDiffElement(BaseDiffElement):
    branch: str | None = None
    labels: list[str]
    kind: str
    id: str
    path: str
    action: DiffAction
    db_id: str = Field(exclude=True)
    rel_id: str | None = Field(None, exclude=True)
    changed_at: Timestamp | None = None
    attributes: dict[str, NodeAttributeDiffElement] = Field(default_factory=dict)


class RelationshipEdgeNodeDiffElement(BaseDiffElement):
    id: str
    db_id: str | None = Field(None, exclude=True)
    rel_id: str | None = Field(None, exclude=True)
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
    changed_at: Timestamp | None = None
    paths: list[str]
    conflict_paths: list[str]

    def get_node_id_by_kind(self, kind: str) -> str | None:
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


class ModifiedPath(BaseModel):
    type: ModifiedPathType
    node_id: str
    path_type: PathType
    kind: str
    element_name: str | None = None
    property_name: str | None = None
    peer_id: str | None = None
    action: DiffAction
    change: ValueElement | None = None

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
    property_name: str | None = None
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


class BranchDiffFile(BaseModel):
    branch: str
    location: str
    action: DiffAction


class BranchDiffRepository(BaseModel):
    branch: str
    id: str
    display_name: str | None = None
    commit_from: str
    commit_to: str
    files: list[BranchDiffFile] = Field(default_factory=list)


class BranchDiffArtifactStorage(BaseModel):
    storage_id: str
    checksum: str


class ArtifactTarget(BaseModel):
    id: str
    kind: str
    display_label: str | None = None


class BranchDiffArtifact(BaseModel):
    branch: str
    id: str
    display_label: str | None = None
    action: DiffAction
    target: ArtifactTarget | None = None
    item_new: BranchDiffArtifactStorage | None = None
    item_previous: BranchDiffArtifactStorage | None = None
