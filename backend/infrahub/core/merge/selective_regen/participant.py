from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from .models import CascadeRole, PlannedRegeneration

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .definition_selector.base import DefinitionSelectorBase
    from .models import CascadeOutput, CascadeSourceOutput, RegenerationRequest


class CascadeParticipant(ABC):
    """A selector paired with its place in the merge regeneration cascade.

    Selection is the selector's concern; capturing output for the cascade is a separate one. A
    participant binds the two so a source and a terminal differ by composition rather than a flag.
    """

    role: CascadeRole

    def __init__(self, selector: DefinitionSelectorBase[Any, Any]) -> None:
        self.selector = selector

    def to_entry(self, requests: Sequence[RegenerationRequest]) -> PlannedRegeneration:
        """Turn this participant's selected requests into a plan entry carrying its cascade output."""
        return PlannedRegeneration(
            workflow=self.selector.workflow,
            cascade_role=self.role,
            requests=requests,
            output=self._capture(requests),
        )

    @abstractmethod
    def _capture(self, requests: Sequence[RegenerationRequest]) -> CascadeSourceOutput | None:
        """The output capture for these requests, or None when nothing downstream reselects from it."""


class CascadeSource(CascadeParticipant):
    """A participant whose output the cascade re-reads to reselect the terminals that consume it."""

    role = CascadeRole.SOURCE

    def __init__(self, selector: DefinitionSelectorBase[Any, Any], *, output: CascadeOutput[Any]) -> None:
        super().__init__(selector)
        self._output = output

    def _capture(self, requests: Sequence[RegenerationRequest]) -> CascadeSourceOutput:
        return self._output.for_requests(requests)


class CascadeTerminal(CascadeParticipant):
    """A participant that ends the cascade -- nothing downstream re-reads what it produces."""

    role = CascadeRole.TERMINAL

    def _capture(self, requests: Sequence[RegenerationRequest]) -> None:  # noqa: ARG002
        return None
