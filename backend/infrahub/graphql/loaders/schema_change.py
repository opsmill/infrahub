"""DataLoaders for the operations and the applications of the schema changes of one request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from aiodataloader import DataLoader

from infrahub.core.schema_change.history_reader import (
    SchemaChangeApplicationRecord,
    SchemaChangeHistoryReader,
    SchemaOperationPage,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class DatabaseSessionOpener(Protocol):
    def __call__(self, read_only: bool = ...) -> InfrahubDatabase: ...


@dataclass(frozen=True)
class OperationPageParams:
    limit: int
    offset: int


class SchemaChangeOperationsDataLoader(DataLoader[str, SchemaOperationPage]):
    """Load one page of the operations of each schema change ID, with one query for all the IDs of a batch."""

    def __init__(
        self, open_session: DatabaseSessionOpener, params: OperationPageParams, *args: Any, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.open_session = open_session
        self.params = params

    async def batch_load_fn(self, keys: list[str]) -> list[SchemaOperationPage]:
        async with self.open_session(read_only=True) as db:
            pages = await SchemaChangeHistoryReader(db=db).list_operations(
                schema_change_ids=keys, limit=self.params.limit, offset=self.params.offset
            )
        return [pages.get(key, SchemaOperationPage(count=0, operations=[])) for key in keys]


class SchemaChangeApplicationsDataLoader(DataLoader[str, list[SchemaChangeApplicationRecord]]):
    """Load the applications of each schema change ID with their migration records, with one query for all the IDs of a batch."""

    def __init__(self, open_session: DatabaseSessionOpener, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.open_session = open_session

    async def batch_load_fn(self, keys: list[str]) -> list[list[SchemaChangeApplicationRecord]]:
        async with self.open_session(read_only=True) as db:
            applications = await SchemaChangeHistoryReader(db=db).list_applications(schema_change_ids=keys)
        return [applications.get(key, []) for key in keys]


class SchemaChangeLoaders:
    """The loaders of one schema change history request, shared by every schema change of its page.

    Each loader opens a read-only session of its own, because graphql-core resolves the nested fields of
    the page concurrently.
    """

    def __init__(self, open_session: DatabaseSessionOpener) -> None:
        self.open_session = open_session
        self.applications = SchemaChangeApplicationsDataLoader(open_session=open_session)
        self._operations: dict[OperationPageParams, SchemaChangeOperationsDataLoader] = {}

    def operations(self, *, limit: int, offset: int) -> SchemaChangeOperationsDataLoader:
        params = OperationPageParams(limit=limit, offset=offset)
        if params not in self._operations:
            self._operations[params] = SchemaChangeOperationsDataLoader(open_session=self.open_session, params=params)
        return self._operations[params]
