"""DataLoaders for the operations, the applications and the migration records of the schema changes of one request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from aiodataloader import DataLoader

from infrahub.core.schema_change.factory import build_schema_change_history_reader
from infrahub.core.schema_change.history_reader import (
    SchemaChangeApplicationPage,
    SchemaChangeMigrationPage,
    SchemaOperationPage,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class DatabaseSessionOpener(Protocol):
    def __call__(self, read_only: bool = ...) -> InfrahubDatabase: ...


@dataclass(frozen=True)
class PageParams:
    limit: int
    offset: int


class SchemaChangeOperationsDataLoader(DataLoader[str, SchemaOperationPage]):
    """Load one page of the operations of each schema change ID, with one query for all the IDs of a batch."""

    def __init__(self, open_session: DatabaseSessionOpener, params: PageParams, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.open_session = open_session
        self.params = params

    async def batch_load_fn(self, keys: list[str]) -> list[SchemaOperationPage]:
        async with self.open_session(read_only=True) as db:
            pages = await build_schema_change_history_reader(db=db).list_operations(
                schema_change_ids=keys, limit=self.params.limit, offset=self.params.offset
            )
        return [pages.get(key, SchemaOperationPage(count=0, operations=[])) for key in keys]


class SchemaChangeApplicationsDataLoader(DataLoader[str, SchemaChangeApplicationPage]):
    """Load one page of the applications of each schema change ID, with one query for all the IDs of a batch."""

    def __init__(self, open_session: DatabaseSessionOpener, params: PageParams, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.open_session = open_session
        self.params = params

    async def batch_load_fn(self, keys: list[str]) -> list[SchemaChangeApplicationPage]:
        async with self.open_session(read_only=True) as db:
            pages = await build_schema_change_history_reader(db=db).list_applications(
                schema_change_ids=keys, limit=self.params.limit, offset=self.params.offset
            )
        return [pages.get(key, SchemaChangeApplicationPage(count=0, applications=[])) for key in keys]


class SchemaChangeMigrationsDataLoader(DataLoader[str, SchemaChangeMigrationPage]):
    """Load one page of the migration records of each application ID, with one query for all the IDs of a batch."""

    def __init__(self, open_session: DatabaseSessionOpener, params: PageParams, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.open_session = open_session
        self.params = params

    async def batch_load_fn(self, keys: list[str]) -> list[SchemaChangeMigrationPage]:
        async with self.open_session(read_only=True) as db:
            pages = await build_schema_change_history_reader(db=db).list_migrations(
                application_ids=keys, limit=self.params.limit, offset=self.params.offset
            )
        return [pages.get(key, SchemaChangeMigrationPage(count=0, migrations=[])) for key in keys]


class SchemaChangeLoaders:
    """The loaders of one schema change history request, shared by every schema change of its page.

    Each loader opens a read-only session of its own, because graphql-core resolves the nested fields of
    the page concurrently. A request has one loader per field and page, so that the records of every
    parent on the page that asks for the same page come from one query.
    """

    def __init__(self, open_session: DatabaseSessionOpener) -> None:
        self.open_session = open_session
        self._operations: dict[PageParams, SchemaChangeOperationsDataLoader] = {}
        self._applications: dict[PageParams, SchemaChangeApplicationsDataLoader] = {}
        self._migrations: dict[PageParams, SchemaChangeMigrationsDataLoader] = {}

    def operations(self, *, limit: int, offset: int) -> SchemaChangeOperationsDataLoader:
        params = PageParams(limit=limit, offset=offset)
        if params not in self._operations:
            self._operations[params] = SchemaChangeOperationsDataLoader(open_session=self.open_session, params=params)
        return self._operations[params]

    def applications(self, *, limit: int, offset: int) -> SchemaChangeApplicationsDataLoader:
        params = PageParams(limit=limit, offset=offset)
        if params not in self._applications:
            self._applications[params] = SchemaChangeApplicationsDataLoader(
                open_session=self.open_session, params=params
            )
        return self._applications[params]

    def migrations(self, *, limit: int, offset: int) -> SchemaChangeMigrationsDataLoader:
        params = PageParams(limit=limit, offset=offset)
        if params not in self._migrations:
            self._migrations[params] = SchemaChangeMigrationsDataLoader(open_session=self.open_session, params=params)
        return self._migrations[params]
