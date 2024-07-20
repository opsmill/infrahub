from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol, Union, runtime_checkable

from typing_extensions import Self

if TYPE_CHECKING:
    from neo4j import AsyncResult, AsyncSession, AsyncTransaction, Record

# pylint: disable=redefined-builtin


@runtime_checkable
class SchemaBranch(Protocol): ...


@runtime_checkable
class Timestamp(Protocol): ...


@runtime_checkable
class NodeSchema(Protocol): ...


@runtime_checkable
class ProfileSchema(Protocol): ...


@runtime_checkable
class Branch(Protocol): ...


@runtime_checkable
class InfrahubDatabase(Protocol):
    is_session: bool
    is_transaction: bool

    def add_schema(self, schema: SchemaBranch, name: Optional[str] = None) -> None: ...
    def start_session(self, read_only: bool = False, schemas: Optional[list[SchemaBranch]] = None) -> Self: ...
    def start_transaction(self, schemas: Optional[list[SchemaBranch]] = None) -> Self: ...
    async def session(self) -> AsyncSession: ...
    async def transaction(self, name: Optional[str]) -> AsyncTransaction: ...
    async def close(self) -> None: ...

    async def execute_query(
        self, query: str, params: Optional[dict[str, Any]] = None, name: Optional[str] = "undefined"
    ) -> list[Record]: ...

    async def execute_query_with_metadata(
        self, query: str, params: Optional[dict[str, Any]] = None, name: Optional[str] = "undefined"
    ) -> tuple[list[Record], dict[str, Any]]: ...

    async def run_query(
        self, query: str, params: Optional[dict[str, Any]] = None, name: Optional[str] = "undefined"
    ) -> AsyncResult: ...

    def render_list_comprehension(self, items: str, item_name: str) -> str: ...
    def render_list_comprehension_with_list(self, items: str, item_names: list[str]) -> str: ...
    def render_uuid_generation(self, node_label: str, node_attr: str) -> str: ...


@runtime_checkable
class CoreNode(Protocol):
    id: str

    def get_id(self) -> str: ...
    def get_kind(self) -> str: ...
    @classmethod
    async def init(
        cls,
        schema: Union[NodeSchema, ProfileSchema, str],
        db: InfrahubDatabase,
        branch: Optional[Union[Branch, str]] = None,
        at: Optional[Union[Timestamp, str]] = None,
    ) -> Self: ...
    async def new(self, db: InfrahubDatabase, id: Optional[str] = None, **kwargs: Any) -> Self: ...
    async def save(self, db: InfrahubDatabase, at: Optional[Timestamp] = None) -> Self: ...
    async def delete(self, db: InfrahubDatabase, at: Optional[Timestamp] = None) -> None: ...
    async def load(
        self,
        db: InfrahubDatabase,
        id: Optional[str] = None,
        db_id: Optional[str] = None,
        updated_at: Optional[Union[Timestamp, str]] = None,
        **kwargs: Any,
    ) -> Self: ...
    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: Optional[dict] = None,
        related_node_ids: Optional[set] = None,
        filter_sensitive: bool = False,
    ) -> dict: ...
    async def render_display_label(self, db: Optional[InfrahubDatabase] = None) -> str: ...
    async def from_graphql(self, data: dict, db: InfrahubDatabase) -> bool: ...
