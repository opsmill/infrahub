from __future__ import annotations

from typing import Any

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template


def is_jinja2_template(display_label: str) -> bool:
    return any(c in display_label for c in "{}")


def extract_jinja2_variables(template_str: str) -> list[str]:
    return InfrahubJinja2Template(template=template_str).get_variables()


async def render_display_label(display_label: str, variable_names: list[str], values: list[Any]) -> str | None:
    if not is_jinja2_template(display_label):
        return values[0] if values and values[0] is not None else None

    variables = dict(zip(variable_names, values, strict=False))
    jinja_template = InfrahubJinja2Template(template=display_label)
    return await jinja_template.render(variables=variables)
