from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from infrahub.core.constants import MutationAction
    from infrahub.core.node import Node

_mutation_context: contextvars.ContextVar[NodeMutationContext | None] = contextvars.ContextVar(
    "node_mutation_context", default=None
)


@dataclass(frozen=True)
class RecordedNode:
    """A node a mutation wrote besides its main node, with what the mutation did to it."""

    node: Node
    action: MutationAction


@dataclass
class NodeMutationContext:
    """Collects the other nodes a mutation writes, each with the action applied, so each one gets its own event.

    Uses Python contextvars for async-safe ambient state. Only active when
    explicitly created with a context manager. Recording is a no-op when
    no context is active.
    """

    recorded_nodes: list[RecordedNode] = field(default_factory=list)
    _token: contextvars.Token[NodeMutationContext | None] | None = None

    def record(self, node: Node, action: MutationAction) -> None:
        self.recorded_nodes.append(RecordedNode(node=node, action=action))

    @classmethod
    def get_current(cls) -> NodeMutationContext | None:
        return _mutation_context.get(None)

    @classmethod
    def record_if_active(cls, node: Node, action: MutationAction) -> None:
        ctx = cls.get_current()
        if ctx is not None:
            ctx.record(node=node, action=action)

    def __enter__(self) -> Self:
        self._token = _mutation_context.set(self)
        return self

    def __exit__(self, *args: object) -> None:
        if self._token is not None:
            _mutation_context.reset(self._token)
