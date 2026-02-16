from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query.standard_node import StandardNodeGetListQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


def _normalize_start_date(value: str) -> str:
    """Expand a bare date (YYYY-MM-DD) to the start of that day in UTC."""
    if len(value) <= 10 and "T" not in value:
        return f"{value}T00:00:00.000000+00:00"
    return value


def _normalize_end_date(value: str) -> str:
    """Expand a bare date (YYYY-MM-DD) to the end of that day in UTC.

    `created_at` is stored as a full ISO timestamp (e.g. ``2026-04-10T14:30:00.123456+00:00``).
    A naive lexicographic compare against ``end_date="2026-04-10"`` would exclude every
    snapshot collected later that day. Expanding the bare date to ``T23:59:59.999999+00:00``
    makes the upper bound day-inclusive.
    """
    if len(value) <= 10 and "T" not in value:
        return f"{value}T23:59:59.999999+00:00"
    return value


class TelemetrySnapshotGetListQuery(StandardNodeGetListQuery):
    name = "telemetry-snapshot-get-list"

    def __init__(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._start_date = start_date
        self._end_date = end_date
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        filters: list[str] = []
        params: dict[str, Any] = {}

        if self._start_date:
            filters.append("n.created_at >= $start_date")
            params["start_date"] = _normalize_start_date(self._start_date)
        if self._end_date:
            filters.append("n.created_at <= $end_date")
            params["end_date"] = _normalize_end_date(self._end_date)

        if filters:
            self.raw_filter = " AND ".join(filters)

        await super().query_init(db=db, **kwargs)
        self.params.update(params)
