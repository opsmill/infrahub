from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from infrahub.core.node import Node

_mutation_context: contextvars.ContextVar[NodeMutationContext | None] = contextvars.ContextVar(
    "node_mutation_context", default=None
)


@dataclass
class NodeMutationContext:
    """Collects nodes created as side effects during node creation.

    Uses Python contextvars for async-safe ambient state. Only active when
    explicitly created with a context manager. Recording is a no-op when
    no context is active.
    """

    side_effect_nodes: list[Node] = field(default_factory=list)
    _token: contextvars.Token[NodeMutationContext | None] | None = None

    def record(self, node: Node) -> None:
        self.side_effect_nodes.append(node)

    @classmethod
    def get_current(cls) -> NodeMutationContext | None:
        return _mutation_context.get(None)

    @classmethod
    def record_if_active(cls, node: Node) -> None:
        ctx = cls.get_current()
        if ctx is not None:
            ctx.record(node)

    def __enter__(self) -> Self:
        self._token = _mutation_context.set(self)
        return self

    def __exit__(self, *args: object) -> None:
        if self._token is not None:
            _mutation_context.reset(self._token)
