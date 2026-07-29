from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from .models import CascadeRole, FullRegeneration, PlannedRegeneration

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .definition_selector.base import DefinitionSelectorBase
    from .models import CascadeSourceOutput, CascadeSourceOutputFactory, RegenerationRequest


class CascadeParticipant[RequestT: RegenerationRequest](ABC):
    """A selector paired with its place in the merge regeneration cascade.

    Selection is the selector's concern; capturing output for the cascade is a separate one. A
    participant binds the two so a source and a terminal differ by composition rather than a flag.
    The request type is carried so a source's output must match the selector it is wired to.
    """

    role: CascadeRole

    def __init__(self, selector: DefinitionSelectorBase[Any, RequestT]) -> None:
        self.selector = selector

    def to_entry(self, requests: Sequence[RequestT]) -> PlannedRegeneration:
        """Turn this participant's selected requests into a plan entry carrying its cascade output."""
        return PlannedRegeneration(
            workflow=self.selector.workflow,
            cascade_role=self.role,
            requests=requests,
            output=self._capture(requests),
        )

    def full_regeneration(self, *, target_branch: str) -> FullRegeneration:
        """The blanket regeneration of this participant's kind, for when selective output is unavailable."""
        return FullRegeneration(
            workflow=self.selector.full_regeneration_workflow,
            parameters=self.selector.full_regeneration_parameters(target_branch=target_branch),
        )

    @abstractmethod
    def _capture(self, requests: Sequence[RequestT]) -> CascadeSourceOutput | None:
        """The output capture for these requests, or None when nothing downstream reselects from it."""


class CascadeSource[RequestT: RegenerationRequest](CascadeParticipant[RequestT]):
    """A participant whose output the cascade re-reads to reselect the terminals that consume it."""

    role = CascadeRole.SOURCE

    def __init__(
        self, selector: DefinitionSelectorBase[Any, RequestT], *, output: CascadeSourceOutputFactory[RequestT]
    ) -> None:
        super().__init__(selector)
        self._output = output

    def _capture(self, requests: Sequence[RequestT]) -> CascadeSourceOutput:
        return self._output.for_requests(requests)


class CascadeTerminal[RequestT: RegenerationRequest](CascadeParticipant[RequestT]):
    """A participant that ends the cascade -- nothing downstream re-reads what it produces."""

    role = CascadeRole.TERMINAL

    def _capture(self, requests: Sequence[RequestT]) -> None:  # noqa: ARG002
        return None
