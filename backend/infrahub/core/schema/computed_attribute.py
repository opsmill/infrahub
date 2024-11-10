from typing import Any, Optional

from pydantic import ConfigDict, Field, model_serializer, model_validator

from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.models import HashableModel


class ComputedAttribute(HashableModel):
    kind: ComputedAttributeKind
    jinja2_template: Optional[str] = Field(
        default=None, description="The Jinja2 template in string format, required when assignment_type=jinja2"
    )
    transform: Optional[str] = Field(
        default=None, description="The Python Transform name or ID, required when assignment_type=transform"
    )
    value: Optional[dict[str, Any]] = Field(
        default=None,
        description="Only used for internal serialization",
    )

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        return {
            "value": {"kind": self.kind.value, "jinja2_template": self.jinja2_template, "transform": self.transform}
        }

    @model_validator(mode="before")
    @classmethod
    def validate_time_from_if_required(cls, values: dict[str, Any]) -> dict[str, Any]:
        value: dict | None = values.get("value")
        if value:
            if "kind" not in values:
                values["kind"] = value.get("kind")
            if "jinja2_template" not in values:
                values["jinja2_template"] = value.get("jinja2_template")
            if "transform" not in values:
                values["transform"] = value.get("transform")

        return values

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
