from dataclasses import dataclass, field
from uuid import uuid4


def str_uuid() -> str:
    return str(uuid4())


@dataclass
class VertexToAdd:
    labels: list[str]
    after_props: dict[str, str | int | bool]
    identifier: str = field(default_factory=str_uuid)


@dataclass
class VertexToUpdate:
    db_id: str
    before_props: dict[str, str | int | bool]
    after_props: dict[str, str | int | bool]


@dataclass
class VertexToDelete:
    db_id: str
    labels: list[str]
    before_props: dict[str, str | int | bool]


@dataclass
class EdgeToAdd:
    from_id: str
    to_id: str
    edge_type: str
    after_props: dict[str, str | int | bool]
    identifier: str = field(default_factory=str_uuid)


@dataclass
class EdgeToUpdate:
    db_id: str
    before_props: dict[str, str | int | bool]
    after_props: dict[str, str | int | bool]


@dataclass
class EdgeToDelete:
    db_id: str
    from_id: str
    to_id: str
    edge_type: str
    before_props: dict[str, str | int | bool]


@dataclass
class PatchPlan:
    name: str
    vertices_to_add: list[VertexToAdd] = field(default_factory=list)
    vertices_to_update: list[VertexToUpdate] = field(default_factory=list)
    vertices_to_delete: list[VertexToDelete] = field(default_factory=list)
    edges_to_add: list[EdgeToAdd] = field(default_factory=list)
    edges_to_update: list[EdgeToUpdate] = field(default_factory=list)
    edges_to_delete: list[EdgeToDelete] = field(default_factory=list)
    added_node_db_id_map: dict[str, str] = field(default_factory=dict)

    def get_database_id_for_added_element(self, abstract_id: str) -> str:
        return self.added_node_db_id_map.get(abstract_id, abstract_id)
