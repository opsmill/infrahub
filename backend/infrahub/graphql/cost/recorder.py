from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.graphql.cost.constants import ESTIMATE_FIELD_PATH

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub.graphql.cost.models import FieldDescription


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
