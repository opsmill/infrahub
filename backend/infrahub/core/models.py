from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# pylint: disable=no-member


class NodeKind(BaseModel):
    namespace: str
    name: str

    def __str__(self):
        return f"{self.namespace}{self.name}"


class SchemaBranchDiff(BaseModel):
    nodes: List[str] = Field(default_factory=list)
    generics: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)

    def to_string(self):
        return ", ".join(self.nodes + self.generics + self.groups)


class SchemaBranchHash(BaseModel):
    main: str
    nodes: Dict[str, str] = Field(default_factory=dict)
    generics: Dict[str, str] = Field(default_factory=dict)
    groups: Dict[str, str] = Field(default_factory=dict)

    def compare(self, other: SchemaBranchHash) -> Optional[SchemaBranchDiff]:
        if other.main == self.main:
            return None

        return SchemaBranchDiff(
            nodes=[key for key, value in other.nodes.items() if key not in self.nodes or self.nodes[key] != value],
            generics=[
                key for key, value in other.generics.items() if key not in self.generics or self.generics[key] != value
            ],
            groups=[key for key, value in other.groups.items() if key not in self.groups or self.groups[key] != value],
        )
