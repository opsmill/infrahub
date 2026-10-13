from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.graphql.cost.constants import ESTIMATE_FIELD_PATH

if TYPE_CHECKING:
    from collections.abc import Awaitable, Iterator, Mapping, Sequence

    from graphql import GraphQLResolveInfo

    from infrahub.graphql.cost.models import FieldDescription

_PAGINATION_KEYS = frozenset({"edges", "node"})


@dataclass
class FieldActual:
    field: FieldDescription | None = None
    """None until a resolver call of the field is recorded."""

    nodes: int = 0
    resolver_calls: int = 0
    database_rows: int = 0


@dataclass
class QueryTotals:
    queries: int = 0
    database_rows: int = 0


class QueryCostRecorder:
    """Work done by one request: totals for each field path, for the counted first step, and for the rest."""

    def __init__(self) -> None:
        self._fields: dict[str, FieldActual] = {}
        self._estimate_queries = QueryTotals()
        self._unattributed = QueryTotals()

    @property
    def fields(self) -> Mapping[str, FieldActual]:
        """Totals for each field path, in the order each path was first recorded."""
        return self._fields

    @property
    def estimate_queries(self) -> QueryTotals:
        return self._estimate_queries

    @property
    def unattributed(self) -> QueryTotals:
        return self._unattributed

    def record_call(self, path: str, field: FieldDescription, nodes: int) -> None:
        actual = self._fields.setdefault(path, FieldActual())
        actual.field = field
        actual.resolver_calls += 1
        actual.nodes += nodes

    def record_query(self, path: str | None, rows: int) -> None:
        """Record one database query and the rows it returned.

        Args:
            path: Path of the field being resolved; the reserved estimate path counts the query for the
                first step, and None counts it as unattributed.

        """
        if path is None:
            self._unattributed.queries += 1
            self._unattributed.database_rows += rows
        elif path == ESTIMATE_FIELD_PATH:
            self._estimate_queries.queries += 1
            self._estimate_queries.database_rows += rows
        else:
            self._fields.setdefault(path, FieldActual()).database_rows += rows


_cost_recorder: ContextVar[QueryCostRecorder | None] = ContextVar("query_cost_recorder", default=None)
_current_field: ContextVar[str | None] = ContextVar("query_cost_current_field", default=None)


def get_cost_recorder() -> QueryCostRecorder | None:
    """Recorder of the request being handled, or None when the request did not ask for the cost details."""
    return _cost_recorder.get()


def get_current_field() -> str | None:
    """Path of the field being resolved, the reserved estimate path, or None outside any field."""
    return _current_field.get()


@contextmanager
def activate_recorder(recorder: QueryCostRecorder) -> Iterator[None]:
    """Record the work done inside the block, including in the tasks it starts, then restore the previous recorder."""
    token = _cost_recorder.set(recorder)
    try:
        yield
    finally:
        _cost_recorder.reset(token)


@contextmanager
def resolving_field(path: str) -> Iterator[None]:
    """Count the rows read inside the block, including in the tasks it starts, for the field path."""
    token = _current_field.set(path)
    try:
        yield
    finally:
        _current_field.reset(token)


def field_path_from_response_keys(keys: Sequence[str | int]) -> str:
    """Join the response keys of a field with '/', without list indexes and the edges and node levels."""
    return "/".join(key for key in keys if isinstance(key, str) and key not in _PAGINATION_KEYS)


def field_path_from_info(info: GraphQLResolveInfo) -> str:
    return field_path_from_response_keys(keys=info.path.as_list())


def count_returned_nodes(result: Mapping[str, Any]) -> int:
    """Count the nodes of a paginated result, or the peer of a single-node result."""
    edges = result.get("edges")
    if edges is not None:
        return len(edges)
    return 0 if result.get("node") is None else 1


async def record_resolver_call(
    recorder: QueryCostRecorder, path: str, field: FieldDescription, body: Awaitable[dict[str, Any]]
) -> dict[str, Any]:
    """Await a resolver body while its field path is current, then record the call and the nodes it returned.

    A body that raises is recorded as a call that returned no nodes, so that the rows it read keep a field.
    """
    nodes = 0
    try:
        with resolving_field(path=path):
            result = await body
        nodes = count_returned_nodes(result=result)
    finally:
        recorder.record_call(path=path, field=field, nodes=nodes)
    return result
