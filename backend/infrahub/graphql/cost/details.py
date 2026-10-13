from __future__ import annotations

from datetime import datetime  # noqa: TC003  (pydantic field type, needs a runtime import)
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from infrahub.core.constants import (
    RelationshipCardinality,  # noqa: TC001  (pydantic field type, needs a runtime import)
)
from infrahub.graphql.cost.constants import QUERY_COST_HEADER, QUERY_COST_HEADER_VALUE
from infrahub.graphql.cost.models import EstimateMode, EstimateReason, EstimateSource

if TYPE_CHECKING:
    from starlette.datastructures import Headers

    from infrahub.graphql.cost.models import (
        CostFigures,
        FieldDescription,
        FieldEstimate,
        QueryEstimate,
        StatisticsPointer,
    )
    from infrahub.graphql.cost.recorder import FieldActual, QueryCostRecorder, QueryTotals


class QueryCostFigures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: int = Field(ge=0)
    resolver_calls: int = Field(ge=0)
    database_rows: int = Field(ge=0)


class QueryCostFieldEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected: QueryCostFigures | None
    worst_case: QueryCostFigures | None
    worst_case_is_bound: bool
    source: EstimateSource | None
    reason: EstimateReason | None


class QueryCostField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    kind: str
    relationship_identifier: str | None
    cardinality: RelationshipCardinality
    estimate: QueryCostFieldEstimate
    actual: QueryCostFigures


class QueryCostTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: int = Field(ge=0)
    database_rows: int = Field(ge=0)


class QueryCostStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch: str
    computed_at: datetime
    version: int = Field(ge=1)


class QueryCostDetails(BaseModel):
    """Content of `extensions.query_cost` in the response to a request that asks for the cost details."""

    model_config = ConfigDict(extra="forbid")

    estimate_mode: EstimateMode
    statistics: QueryCostStatistics | None
    fields: list[QueryCostField]
    estimate_queries: QueryCostTotals
    unattributed: QueryCostTotals


def query_cost_details_requested(headers: Headers) -> bool:
    """Tell whether a request asks for the cost details; the header value is compared without case."""
    return headers.get(QUERY_COST_HEADER, "").lower() == QUERY_COST_HEADER_VALUE


def build_query_cost_details(estimate: QueryEstimate | None, recorder: QueryCostRecorder) -> QueryCostDetails:
    """List the fields of the estimate in tree order, then the other recorded fields in recording order.

    Raises:
        ValueError: When rows were recorded for a field outside the estimate without any resolver call.

    """
    estimates = estimate.estimates if estimate is not None else {}

    fields = [
        _build_field(
            path=path,
            description=field_estimate.field,
            estimate=_build_field_estimate(field_estimate=field_estimate),
            actual=recorder.fields.get(path),
        )
        for path, field_estimate in estimates.items()
    ]
    for path, actual in recorder.fields.items():
        if path in estimates:
            continue
        if actual.field is None:
            raise ValueError(f"Database rows were recorded for the field '{path}' without a resolver call")
        fields.append(
            _build_field(path=path, description=actual.field, estimate=_build_no_statistics_estimate(), actual=actual)
        )

    return QueryCostDetails(
        estimate_mode=estimate.mode if estimate is not None else EstimateMode.STATISTICS_ONLY,
        statistics=_build_statistics(pointer=estimate.statistics if estimate is not None else None),
        fields=fields,
        estimate_queries=_build_totals(totals=recorder.estimate_queries),
        unattributed=_build_totals(totals=recorder.unattributed),
    )


def _build_field(
    path: str, description: FieldDescription, estimate: QueryCostFieldEstimate, actual: FieldActual | None
) -> QueryCostField:
    return QueryCostField(
        path=path,
        kind=description.kind,
        relationship_identifier=description.relationship_identifier,
        cardinality=description.cardinality,
        estimate=estimate,
        actual=QueryCostFigures(
            nodes=actual.nodes if actual is not None else 0,
            resolver_calls=actual.resolver_calls if actual is not None else 0,
            database_rows=actual.database_rows if actual is not None else 0,
        ),
    )


def _build_field_estimate(field_estimate: FieldEstimate) -> QueryCostFieldEstimate:
    return QueryCostFieldEstimate(
        expected=_build_figures(figures=field_estimate.expected),
        worst_case=_build_figures(figures=field_estimate.worst_case),
        worst_case_is_bound=field_estimate.worst_case_is_bound,
        source=field_estimate.source,
        reason=field_estimate.reason,
    )


def _build_no_statistics_estimate() -> QueryCostFieldEstimate:
    return QueryCostFieldEstimate(
        expected=None,
        worst_case=None,
        worst_case_is_bound=False,
        source=None,
        reason=EstimateReason.NO_STATISTICS,
    )


def _build_figures(figures: CostFigures | None) -> QueryCostFigures | None:
    if figures is None:
        return None
    return QueryCostFigures(
        nodes=figures.nodes, resolver_calls=figures.resolver_calls, database_rows=figures.database_rows
    )


def _build_statistics(pointer: StatisticsPointer | None) -> QueryCostStatistics | None:
    if pointer is None:
        return None
    return QueryCostStatistics(branch=pointer.branch, computed_at=pointer.computed_at, version=pointer.version)


def _build_totals(totals: QueryTotals) -> QueryCostTotals:
    return QueryCostTotals(queries=totals.queries, database_rows=totals.database_rows)
