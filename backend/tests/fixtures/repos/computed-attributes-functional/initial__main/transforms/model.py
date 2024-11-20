from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Pitch:
    name: str
    color: str
    description: str

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> Pitch:
        node = data["TestingTShirt"]["edges"][0]["node"]
        color = node["color"]["node"]
        return cls(
            name=node["name"]["value"],
            color=color["name"]["value"],
            description=color["description"]["value"],
        )

    def render(self) -> str:
        return f"Buy your {self.name} t-shirt today. Look great in {self.description.lower()}"
