from dataclasses import dataclass, field
from uuid import uuid4

PropertyPrimitives = str | bool | int | float | None


def str_uuid() -> str:
    return str(uuid4())


@dataclass
class VertexToAdd:
    labels: list[str]
    after_props: dict[str, PropertyPrimitives]
    identifier: str = field(default_factory=str_uuid)


@dataclass
class VertexToUpdate:
    db_id: str
    before_props: dict[str, PropertyPrimitives]
    after_props: dict[str, PropertyPrimitives]


@dataclass
class VertexToDelete:
    db_id: str
    labels: list[str]
    before_props: dict[str, PropertyPrimitives]


@dataclass
class EdgeToAdd:
    from_id: str
    to_id: str
    edge_type: str
    after_props: dict[str, PropertyPrimitives]
    identifier: str = field(default_factory=str_uuid)


@dataclass
class EdgeToUpdate:
    db_id: str
    before_props: dict[str, PropertyPrimitives]
    after_props: dict[str, PropertyPrimitives]


@dataclass
class EdgeToDelete:
    db_id: str
    from_id: str
    to_id: str
    edge_type: str
    before_props: dict[str, PropertyPrimitives]


@dataclass
class PatchPlan:
    name: str
    vertices_to_add: list[VertexToAdd] = field(default_factory=list)
    vertices_to_update: list[VertexToUpdate] = field(default_factory=list)
    vertices_to_delete: list[VertexToDelete] = field(default_factory=list)
    edges_to_add: list[EdgeToAdd] = field(default_factory=list)
    edges_to_update: list[EdgeToUpdate] = field(default_factory=list)
    edges_to_delete: list[EdgeToDelete] = field(default_factory=list)
    added_element_db_id_map: dict[str, str] = field(default_factory=dict)
    deleted_db_ids: set[str] = field(default_factory=set)
    reverted_deleted_db_id_map: dict[str, str] = field(default_factory=dict)

    def get_database_id_for_added_element(self, abstract_id: str) -> str:
        return self.added_element_db_id_map.get(abstract_id, abstract_id)

    def has_element_been_added(self, identifier: str) -> bool:
        return identifier in self.added_element_db_id_map

    @property
    def added_vertices(self) -> list[VertexToAdd]:
        return [v for v in self.vertices_to_add if self.has_element_been_added(v.identifier)]

    @property
    def added_edges(self) -> list[EdgeToAdd]:
        return [e for e in self.edges_to_add if self.has_element_been_added(e.identifier)]

    @property
    def deleted_vertices(self) -> list[VertexToDelete]:
        return [v for v in self.vertices_to_delete if v.db_id in self.deleted_db_ids]

    @property
    def deleted_edges(self) -> list[EdgeToDelete]:
        return [e for e in self.edges_to_delete if e.db_id in self.deleted_db_ids]

    def drop_added_db_ids(self, db_ids_to_drop: set[str]) -> None:
        self.added_element_db_id_map = {
            k: v for k, v in self.added_element_db_id_map.items() if v not in db_ids_to_drop
        }

    def drop_deleted_db_ids(self, db_ids_to_drop: set[str]) -> None:
        self.deleted_db_ids -= db_ids_to_drop
