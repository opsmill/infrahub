import re
from typing import Optional

from pydantic import field_validator

from pydantic import Field
from infrahub.core.models import HashableModel

HTML_COLOR = re.compile(r"#[0-9a-fA-F]{6}\b")


class DropdownChoice(HashableModel):
    name: str = Field(..., description="The name of the choice, must be unique within the dropdown.")
    description: str | None = Field(None, description="The description of the choice.")
    color: str | None = Field(None, description="The color of the choice.")
    label: str | None = Field(None, description="The label of the choice.")

    _sort_by: list[str] = ["name"]

    @field_validator("color")
    @classmethod
    def kind_options(cls, v: str) -> str:
        if not v:
            return v
        if isinstance(v, str) and HTML_COLOR.match(v):
            return v.lower()

        raise ValueError("Color must be a valid HTML color code")
