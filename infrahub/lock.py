from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import infrahub.config as config


@dataclass
class Registry:
    locks: dict = field(default_factory=dict)

    def get(self, name: str):
        if name not in self.locks:
            self.locks[name] = asyncio.Lock()
        return self.locks[name]


registry = Registry()
