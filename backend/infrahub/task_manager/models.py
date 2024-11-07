from collections import defaultdict
from typing import DefaultDict
from uuid import UUID

from prefect.client.schemas.objects import Log as PrefectLog
from pydantic import BaseModel, Field

from .constants import LOG_LEVEL_MAPPING


class RelatedNodesInfo(BaseModel):
    id: dict[UUID, str] = Field(default_factory=dict)
    kind: dict[UUID, str | None] = Field(default_factory=dict)

    def get_unique_related_node_ids(self) -> list[str]:
        return list(set(list(self.id.values())))


class FlowLogs(BaseModel):
    logs: DefaultDict[UUID, list[PrefectLog]] = Field(default_factory=lambda: defaultdict(list))

    def to_graphql(self, flow_id: UUID) -> list[dict]:
        return [
            {
                "node": {
                    "message": log.message,
                    "severity": LOG_LEVEL_MAPPING.get(log.level, "error"),
                    "timestamp": log.timestamp.to_iso8601_string(),
                }
            }
            for log in self.logs[flow_id]
        ]


class FlowProgress(BaseModel):
    data: dict[UUID, float] = Field(default_factory=dict)
