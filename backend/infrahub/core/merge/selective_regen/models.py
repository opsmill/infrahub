from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
    from infrahub.git.models import RequestArtifactDefinitionGenerate
    from infrahub.message_bus.types import ProposedChangeArtifactDefinition


type DefinitionModel = ProposedChangeGeneratorDefinition | ProposedChangeArtifactDefinition
"""A definition the merge regeneration selects over: a generator or an artifact definition."""


@dataclass(frozen=True)
class LoadedDefinition[DefinitionT: DefinitionModel]:
    """A candidate definition paired with the id of the group it targets."""

    definition: DefinitionT
    group_id: str


@dataclass(frozen=True)
class SelectiveRegenerationPlan:
    """The generator runs and artifact generations a merge follow-up should dispatch."""

    generator_runs: list[RequestGeneratorDefinitionRun]
    artifact_generates: list[RequestArtifactDefinitionGenerate]


@dataclass(frozen=True)
class GateResult:
    """The outcome of the definition-level selection gate.

    ``managed_branch`` is the wide signal (query or definition/fingerprint change) that forces
    every member to regenerate. ``selected`` is whether the definition is dispatched at all.
    """

    managed_branch: bool
    selected: bool
