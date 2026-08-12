from __future__ import annotations

from typing import Any

from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute


def computed_jinja2_attr(name: str, template: str, **overrides: Any) -> AttributeSchema:
    """Build a read-only Text attribute computed from a Jinja2 template.

    Defaults suit a required, unique computed attribute; pass overrides such as
    `unique=False` or `optional=True` for other shapes.
    """
    params: dict[str, Any] = {
        "kind": "Text",
        "read_only": True,
        "unique": True,
        "optional": False,
        "computed_attribute": ComputedAttribute(kind=ComputedAttributeKind.JINJA2, jinja2_template=template),
    }
    params.update(overrides)
    return AttributeSchema(name=name, **params)
