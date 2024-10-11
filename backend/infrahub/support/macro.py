from __future__ import annotations

from typing import Any

from jinja2 import TemplateSyntaxError, meta, nodes
from jinja2.sandbox import SandboxedEnvironment

ALLOWED_FILTERS = ["lower", "upper"]


class MacroDefinition:
    def __init__(self, macro: str) -> None:
        self.macro = macro
        self.env = SandboxedEnvironment()
        self._filters: list[str] = []
        self._variables: list[str] = []
        self.template = self._parse_template()

    def _parse_template(self) -> nodes.Template:
        try:
            self.env.globals = {}
            template = self.env.parse(self.macro)
            if any(node.__class__.__name__ in ["Call", "Import", "Include"] for node in template.body):
                raise ValueError("Forbidden code found in the macro")

        except TemplateSyntaxError as exc:
            raise ValueError("Failed to parse the macro: {exc}") from exc

        for node in template.find_all(nodes.Filter):
            if node.name not in ALLOWED_FILTERS:
                raise ValueError(f"The '{node.name}' filter isn't allowed to be used")
            self._filters.append(node.name)

        self._variables = list(meta.find_undeclared_variables(template))

        return template

    def render(self, variables: dict[str, Any]) -> str:
        template = self.env.from_string(self.macro)
        return template.render(variables)

    @property
    def filters(self) -> list[str]:
        return self._filters

    @property
    def variables(self) -> list[str]:
        return self._variables
