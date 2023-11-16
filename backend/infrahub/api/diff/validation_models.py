from typing import Any, Dict, Optional

from pydantic import BaseModel, root_validator, validator

from infrahub.core.branch import Branch
from infrahub.core.timestamp import Timestamp


class DiffQueryValidated(BaseModel):
    branch: Branch
    time_from: Optional[Timestamp]
    time_to: Optional[Timestamp]
    branch_only: bool

    class Config:
        arbitrary_types_allowed = True

    @validator("time_from", "time_to", pre=True)
    def validate_time(cls, value: Optional[str]) -> Optional[Timestamp]:
        if not value:
            return None
        return Timestamp(value)

    @root_validator(skip_on_failure=True)
    def validate_time_from_if_required(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        branch: Optional[Branch] = values.get("branch")
        time_from: Optional[Timestamp] = values.get("time_from")
        if getattr(branch, "is_default", False) and not time_from:
            raise ValueError(f"time_from is mandatory when diffing on the default branch `{branch.name}`.")
        time_to: Optional[Timestamp] = values.get("time_to")
        if time_to and time_from and time_to < time_from:
            raise ValueError("time_from and time_to are not a valid time range")
        return values
