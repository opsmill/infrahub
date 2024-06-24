from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from infrahub.core.branch import Branch
from infrahub.core.timestamp import Timestamp


class DiffQueryValidated(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    branch: Branch
    time_from: Optional[str] = None
    time_to: Optional[str] = None
    branch_only: bool

    @field_validator("time_from", "time_to", mode="before")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        Timestamp(value)
        return value

    @model_validator(mode="before")
    @classmethod
    def validate_time_from_if_required(cls, values: dict[str, Any]) -> dict[str, Any]:
        branch: Optional[Branch] = values.get("branch")
        time_from: Optional[Timestamp] = values.get("time_from")
        if getattr(branch, "is_default", False) and not time_from:
            branch_name = getattr(branch, "name", "")
            raise ValueError(f"time_from is mandatory when diffing on the default branch `{branch_name}`.")
        time_to: Optional[Timestamp] = values.get("time_to")
        if time_to and time_from and time_to < time_from:
            raise ValueError("time_from and time_to are not a valid time range")
        return values
