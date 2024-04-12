from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class NodeInfo(Protocol):
    def get_kind(self) -> str:
        raise NotImplementedError()

    def get_id(self) -> str:
        raise NotImplementedError()
