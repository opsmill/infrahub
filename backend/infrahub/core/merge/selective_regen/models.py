from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.timestamp import Timestamp
    from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
    from infrahub.git.models import RequestArtifactDefinitionGenerate
    from infrahub.message_bus.types import ProposedChangeArtifactDefinition
    from infrahub.workflows.models import WorkflowDefinition


type DefinitionModel = ProposedChangeGeneratorDefinition | ProposedChangeArtifactDefinition
"""A definition the merge regeneration selects over: a generator or an artifact definition."""

type RegenerationRequest = RequestGeneratorDefinitionRun | RequestArtifactDefinitionGenerate
"""A request a selector emits for one definition it decided to regenerate."""


class CascadeRole(Enum):
    """A selector's role in the merge regeneration cascade, which orders how the follow-up runs it.

    A ``SOURCE`` produces output that the cascade re-reads, so its runs must complete and have their
    writes captured before the terminals are selected. A ``TERMINAL`` is the end of the chain -- nothing
    downstream re-reads its output -- so it is dispatched fire-and-forget afterwards.
    """

    SOURCE = "source"
    TERMINAL = "terminal"


class CascadeSourceOutput[RequestT](Protocol):
    """Captures the diff of what a cascade source's requests wrote once they have run.

    Given the requests the source selected, it produces the diff of their own writes so the terminals
    that read them can be reselected, without the follow-up needing to know how that output is located.
    Bound to its capturer at wiring time; the requests scope the capture and arrive per run.
    """

    async def capture(self, *, since: Timestamp, requests: Sequence[RequestT]) -> list[NodeDiff]: ...


@dataclass(frozen=True)
class LoadedDefinition[DefinitionT: DefinitionModel]:
    """A candidate definition paired with the id of the group it targets."""

    definition: DefinitionT
    group_id: str


@dataclass(frozen=True)
class PlannedRegeneration:
    """One selector's selected requests, tagged with the workflow and dispatch mode that run them."""

    workflow: WorkflowDefinition
    cascade_role: CascadeRole
    requests: Sequence[RegenerationRequest]
    output: CascadeSourceOutput[Any] | None = None
    """How to capture this entry's output when it is a cascade source; None for a terminal."""


@dataclass(frozen=True)
class SelectiveRegenerationPlan:
    """What a merge follow-up should dispatch, one entry per selector that produced requests."""

    entries: list[PlannedRegeneration]

    def for_role(self, cascade_role: CascadeRole) -> list[PlannedRegeneration]:
        """Return the entries whose selector plays the given cascade role, in selector order."""
        return [entry for entry in self.entries if entry.cascade_role is cascade_role]


@dataclass(frozen=True)
class FullRegeneration:
    """A blanket regeneration submission for one kind, ignoring any selective narrowing.

    Dispatched when a cascade source's output is unavailable, so every definition of a terminal kind
    is regenerated rather than only the ones the diff would have selected.
    """

    workflow: WorkflowDefinition
    parameters: dict[str, Any]


@dataclass(frozen=True)
class GateResult:
    """The outcome of the definition-level selection gate.

    ``regenerate_all_members`` is the wide signal (a query or definition/fingerprint change) that
    forces every member to regenerate rather than only the impacted subset. ``selected`` is whether
    the definition is dispatched at all.
    """

    regenerate_all_members: bool
    selected: bool
