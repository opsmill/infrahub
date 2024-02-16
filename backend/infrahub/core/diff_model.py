from typing import Any, Dict, List, Optional

from pydantic.v1 import BaseModel, Field

from infrahub.core.constants import DiffAction
from infrahub.core.timestamp import Timestamp


class BaseDiffElement(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    # def to_graphql(self) -> Dict[str, Any]:
    #     """Recursively Export the model to a dict for GraphQL.
    #     The main rules of convertion are:
    #         - Ignore the fields mark as exclude=True
    #         - Convert the Dict in List
    #     """
    #     resp: Dict[str, Any] = {}
    #     for key, value in self:
    #         if isinstance(value, BaseModel):
    #             resp[key] = value.to_graphql()  # type: ignore[attr-defined]
    #         elif isinstance(value, dict):
    #             resp[key] = [item.to_graphql() for item in value.values()]
    #         elif self.__fields__[key].field_info.exclude:
    #             continue
    #         elif isinstance(value, Enum):
    #             resp[key] = value.value
    #         elif isinstance(value, Timestamp):
    #             resp[key] = value.to_string()
    #         else:
    #             resp[key] = value

    #     return resp


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
    branch: Optional[str] = None
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

    # def to_graphql(self) -> Dict[str, Union[str, List[str]]]:
    #     return {
    #         "branch": self.branch,
    #         "node": self.node,
    #         "kind": self.kind,
    #         "actions": [action.value for action in self.actions],
    #     }
