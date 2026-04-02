from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator

from infrahub.constants.enums import OrderByField, OrderDirection
from infrahub.core.node.standard import StandardNode, StandardNodeOrdering
from infrahub.core.query.standard_node import StandardNodeGetListQuery

from .constants import (
    REMOTE_SEND_STATUS_FAILED,
    REMOTE_SEND_STATUS_PENDING,
    REMOTE_SEND_STATUS_SENT,
    REMOTE_SEND_STATUS_SKIPPED,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

VALID_REMOTE_SEND_STATUSES = {
    REMOTE_SEND_STATUS_PENDING,
    REMOTE_SEND_STATUS_SENT,
    REMOTE_SEND_STATUS_SKIPPED,
    REMOTE_SEND_STATUS_FAILED,
}


class TelemetrySnapshot(StandardNode):
    kind: str
    payload_format: str
    deployment_id: str
    infrahub_version: str
    data: dict[str, Any]
    checksum: str
    remote_send_status: str = Field(default=REMOTE_SEND_STATUS_PENDING)

    @field_validator("kind")
    @classmethod
    def kind_must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("kind must be a non-empty string")
        return v

    @field_validator("payload_format")
    @classmethod
    def payload_format_must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("payload_format must be a non-empty string")
        return v

    @field_validator("checksum")
    @classmethod
    def checksum_must_be_valid_sha256(cls, v: str) -> str:
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("checksum must be a 64-character lowercase hex string (SHA-256)")
        return v

    @field_validator("remote_send_status")
    @classmethod
    def remote_send_status_must_be_valid(cls, v: str) -> str:
        if v not in VALID_REMOTE_SEND_STATUSES:
            raise ValueError(f"remote_send_status must be one of: {', '.join(sorted(VALID_REMOTE_SEND_STATUSES))}")
        return v

    @field_validator("data")
    @classmethod
    def data_must_be_non_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("data must be a non-empty dict")
        return v

    @classmethod
    async def get_list_filtered(
        cls,
        db: InfrahubDatabase,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[TelemetrySnapshot]:
        filters: list[str] = []
        extra_params: dict[str, Any] = {}

        if start_date:
            filters.append("n.created_at >= $start_date")
            extra_params["start_date"] = start_date
        if end_date:
            filters.append("n.created_at <= $end_date")
            extra_params["end_date"] = end_date

        raw_filter = " AND ".join(filters) if filters else None

        node_ordering = StandardNodeOrdering(
            order_by=OrderByField.CREATED_AT,
            direction=OrderDirection.DESC,
        )

        query = await TelemetrySnapshotGetListQuery.init(
            db=db,
            node_class=cls,
            node_ordering=node_ordering,
            limit=limit,
            offset=offset,
            raw_filter=raw_filter,
            extra_params=extra_params,
        )
        await query.execute(db=db)

        return [cls.from_db(result.get_node("n")) for result in query.get_results()]


class TelemetrySnapshotGetListQuery(StandardNodeGetListQuery):
    name = "telemetry-snapshot-get-list"

    def __init__(
        self,
        raw_filter: str | None = None,
        extra_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._instance_raw_filter = raw_filter
        self._extra_params = extra_params or {}
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        if self._instance_raw_filter:
            self.raw_filter = self._instance_raw_filter
        await super().query_init(db=db, **kwargs)
        self.params.update(self._extra_params)
