from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ContextUnit(str, Enum):
    COUNT = "count"
    TIME = "msec"  # time in milliseconds
    MEMORY = "memory"  # memory in bytes
    DISK = "disk"  # disk in bytes


class MeasurementDefinition(BaseModel):
    name: str
    description: str
    dimensions: list[str] = Field(default_factory=dict)
    unit: ContextUnit


class InfrahubResultContext(BaseModel):
    name: str
    value: int | float | str
    unit: ContextUnit


class InfrahubActiveMeasurementItem(BaseModel):
    definition: MeasurementDefinition
    start_time: datetime = datetime.now(UTC)
    context: dict[str, Any] = Field(default_factory=dict)


class InfrahubMeasurementItem(BaseModel):
    name: str
    value: int | float | str
    unit: ContextUnit
    context: dict[str, Any] = Field(default_factory=dict)
