from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class Registry:
    locks: dict = field(default_factory=dict)

    def get(self, name: str):
        if name not in self.locks:
            self.locks[name] = asyncio.Lock()
        return self.locks[name]

    def get_branch_schema_update(self):
        return self.get("branch-schema-update")


registry = Registry()
