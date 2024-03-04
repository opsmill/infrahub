import re
from typing import Optional

from pydantic import field_validator

from infrahub.core.models import HashableModel

HTML_COLOR = re.compile(r"#[0-9a-fA-F]{6}\b")


class DropdownChoice(HashableModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    label: Optional[str] = None

    _sort_by: list[str] = ["name"]

    @field_validator("color")
    @classmethod
    def kind_options(cls, v: str) -> str:
        if not v:
            return v
        if isinstance(v, str) and HTML_COLOR.match(v):
            return v.lower()

        raise ValueError("Color must be a valid HTML color code")
