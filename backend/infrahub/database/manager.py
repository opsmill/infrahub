from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import InfrahubDatabase
    from .index import IndexManagerBase


class DatabaseManager(ABC):
    index: IndexManagerBase

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db
