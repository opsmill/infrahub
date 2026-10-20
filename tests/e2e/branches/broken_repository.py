from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokenRepository:
    branch: str
    repository_name: str
    repository_id: str
