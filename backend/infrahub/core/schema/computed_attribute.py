from typing import Any

from pydantic import ConfigDict, Field, model_serializer

from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.models import HashableModel


class ComputedAttribute(HashableModel):
    kind: ComputedAttributeKind
    jinja2_template: str | None = Field(
        default=None, description="The Jinja2 template in string format, required when assignment_type=jinja2"
    )
    transform: str | None = Field(
        default=None, description="The Python Transform name or ID, required when assignment_type=transform"
    )

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "jinja2_template": self.jinja2_template, "transform": self.transform}

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"kind": {"const": "Jinja2"}}},
                    "then": {
                        "required": ["jinja2_template"],
                        "properties": {
                            "jinja2_template": {
                                "type": "string",
                                "minLength": 1,
                            }
                        },
                    },
                },
                {
                    "if": {"properties": {"kind": {"const": "TransformPython"}}},
                    "then": {
                        "required": ["transform"],
                        "properties": {
                            "transform": {
                                "type": "string",
                                "minLength": 1,
                            }
                        },
                    },
                },
            ]
        },
    )
