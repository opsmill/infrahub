from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Union

from pydantic import BaseModel, Field


class ContextUnit(str, Enum):
    COUNT = "count"
    TIME = "msec"  # time in milliseconds
    MEMORY = "memory"  # memory in bytes
    DISK = "disk"  # disk in bytes


class MeasurementDefinition(BaseModel):
    name: str
    description: str
    dimensions: list[str] = Field(default_factory=list)
    unit: ContextUnit


class InfrahubResultContext(BaseModel):
    name: str
    value: Union[int, float, str]
    unit: ContextUnit


class InfrahubActiveMeasurementItem(BaseModel):
    definition: MeasurementDefinition
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context: dict[str, Any] = Field(default_factory=dict)


class InfrahubMeasurementItem(BaseModel):
    name: str
    value: Union[int, float, str]
    unit: ContextUnit
    context: dict[str, Any] = Field(default_factory=dict)
