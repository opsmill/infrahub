from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from infrahub.core.node import Node

_creation_context: contextvars.ContextVar[NodeCreationContext | None] = contextvars.ContextVar(
    "node_creation_context", default=None
)


@dataclass
class NodeCreationContext:
    """Collects nodes created as side effects during node creation.

    Uses Python contextvars for async-safe ambient state. Only active when
    explicitly created with a context manager. Recording is a no-op when
    no context is active.
    """

    side_effect_nodes: list[Node] = field(default_factory=list)

    def record(self, node: Node) -> None:
        self.side_effect_nodes.append(node)

    @classmethod
    def get_current(cls) -> NodeCreationContext | None:
        return _creation_context.get(None)

    @classmethod
    def record_if_active(cls, node: Node) -> None:
        ctx = cls.get_current()
        if ctx is not None:
            ctx.record(node)

    def __enter__(self) -> Self:
        self._token = _creation_context.set(self)
        return self

    def __exit__(self, *args: object) -> None:
        _creation_context.reset(self._token)
