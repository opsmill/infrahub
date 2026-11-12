from __future__ import annotations

from pydantic import Field

from infrahub.core.constants import DEFAULT_NAME_MAX_LENGTH, DEFAULT_NAME_MIN_LENGTH, NAME_REGEX
from infrahub.core.models import HashableModel


class ContainerSchema(HashableModel):
    name: str = Field(..., pattern=NAME_REGEX, min_length=DEFAULT_NAME_MIN_LENGTH, max_length=DEFAULT_NAME_MAX_LENGTH)
    label: str
    description: str | None = None
    order_weight: int | None = None
    collapsible: bool = True
    collapsed: bool = False
    inherited: bool = False

    _sort_by: list[str] = ["name"]
