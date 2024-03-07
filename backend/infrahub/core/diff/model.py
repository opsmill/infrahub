from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from infrahub.core.constants import (
    DiffAction,
    PathType,
)
from infrahub.core.timestamp import Timestamp


class RelationshipPath(BaseModel):
    paths: List[str] = Field(default_factory=list)
    conflict_paths: List[str] = Field(default_factory=list)


class BaseDiffElement(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    def to_graphql(self) -> Dict[str, Any]:
        """Recursively Export the model to a dict for GraphQL.
        The main rules of convertion are:
            - Ignore the fields mark as exclude=True
            - Convert the Dict in List
        """
        resp: Dict[str, Any] = {}
        for key, value in self:
            if isinstance(value, BaseModel):
                resp[key] = value.to_graphql()  # type: ignore[attr-defined]
            elif isinstance(value, dict):
                resp[key] = [item.to_graphql() for item in value.values()]
            elif self.model_fields[key].exclude:
                continue
            elif isinstance(value, Enum):
                resp[key] = value.value
            elif isinstance(value, Timestamp):
                resp[key] = value.to_string()
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
    properties: Dict[str, PropertyDiffElement]


class NodeDiffElement(BaseDiffElement):
    branch: Optional[str] = None
    labels: List[str]
    kind: str
    id: str
    path: str
    action: DiffAction
    db_id: str = Field(exclude=True)
    rel_id: Optional[str] = Field(None, exclude=True)
    changed_at: Optional[Timestamp] = None
    attributes: Dict[str, NodeAttributeDiffElement]


class RelationshipEdgeNodeDiffElement(BaseDiffElement):
    id: str
    db_id: Optional[str] = Field(None, exclude=True)
    rel_id: Optional[str] = Field(None, exclude=True)
    labels: List[str]
    kind: str


class RelationshipDiffElement(BaseDiffElement):
    branch: str
    id: str
    db_id: str = Field(exclude=True)
    name: str
    action: DiffAction
    nodes: Dict[str, RelationshipEdgeNodeDiffElement]
    properties: Dict[str, PropertyDiffElement]
    changed_at: Optional[Timestamp] = None
    paths: List[str]
    conflict_paths: List[str]

    def get_node_id_by_kind(self, kind: str) -> Optional[str]:
        ids = [rel.id for rel in self.nodes.values() if rel.kind == kind]
        if ids:
            return ids[0]
        return None


class FileDiffElement(BaseDiffElement):
    branch: str
    location: str
    repository: str
    action: DiffAction
    commit_from: str
    commit_to: str

    def __hash__(self) -> int:
        return hash((type(self),) + tuple(self.__dict__.values()))


class DiffSummaryElement(BaseModel):
    branch: str = Field(..., description="The branch where the change occured")
    node: str = Field(..., description="The unique ID of the node")
    kind: str = Field(..., description="The kind of the node as defined by its namespace and name")
    actions: List[DiffAction] = Field(..., description="A list of actions on this node.")

    def to_graphql(self) -> Dict[str, Union[str, List[str]]]:
        return {
            "branch": self.branch,
            "node": self.node,
            "kind": self.kind,
            "actions": [action.value for action in self.actions],
        }


class ModifiedPath(BaseModel):
    type: str
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
        identifier = f"{self.type}/{self.node_id}"
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


class ObjectConflict(BaseModel):
    name: str
    type: str
    kind: str
    id: str

    def to_conflict_dict(self) -> Dict[str, Any]:
        return self.dict()


class DataConflict(ObjectConflict):
    conflict_path: str
    path: str
    path_type: PathType
    property_name: Optional[str] = None
    change_type: str
    changes: List[BranchChanges] = Field(default_factory=list)

    def to_conflict_dict(self) -> Dict[str, Any]:
        conflict_dict = self.dict(exclude={"path_type"})
        conflict_dict["path_type"] = self.path_type.value
        return conflict_dict

    def __str__(self) -> str:
        return self.path


class SchemaConflict(ObjectConflict):
    path: str
    branch: str
    value: str
