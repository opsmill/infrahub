from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ElementData = dict[str, Any]
"""One node or generic in the schema file format, as the load accepts it."""


@dataclass
class ExportDocument:
    """The user-defined schema of some namespaces, before it is wrapped with the file format version."""

    generics: list[ElementData] = field(default_factory=list)
    nodes: list[ElementData] = field(default_factory=list)

    @property
    def namespaces(self) -> list[str]:
        return sorted({element["namespace"] for element in self.generics + self.nodes})

    def sections(self) -> dict[str, list[ElementData]]:
        return {"generics": self.generics, "nodes": self.nodes}
