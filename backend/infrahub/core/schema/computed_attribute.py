from typing import Optional

from pydantic import ConfigDict, Field

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
