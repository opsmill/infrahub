from __future__ import annotations

from infrahub.core.merge.selective_regen.models import CascadeRole
from infrahub.core.merge.selective_regen.participant import CascadeSource, CascadeTerminal
from infrahub.generators.models import RequestGeneratorDefinitionRun
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE, REQUEST_GENERATOR_DEFINITION_RUN
from tests.helpers.selective_regen import ArtifactForcingSelector, GeneratorForcingSelector, StubCascadeSourceOutput


def test_source_entry_carries_its_output() -> None:
    """A source's entry is tagged SOURCE and carries the output it was wired with."""
    output = StubCascadeSourceOutput()
    selector = GeneratorForcingSelector(definitions=[], member_ids=[], subscriber_by_member={})
    participant = CascadeSource[RequestGeneratorDefinitionRun](selector, output=output)
    requests: list[RequestGeneratorDefinitionRun] = []

    entry = participant.to_entry(requests)

    assert participant.role is CascadeRole.SOURCE
    assert entry.workflow is REQUEST_GENERATOR_DEFINITION_RUN
    assert entry.cascade_role is CascadeRole.SOURCE
    assert entry.requests is requests
    assert entry.output is output


def test_terminal_entry_carries_no_output() -> None:
    """A terminal's entry is tagged TERMINAL and carries no output, since nothing reselects from it."""
    selector = ArtifactForcingSelector(definitions=[], member_ids=[], subscriber_by_member={})
    participant = CascadeTerminal(selector)

    entry = participant.to_entry([])

    assert participant.role is CascadeRole.TERMINAL
    assert entry.workflow is REQUEST_ARTIFACT_DEFINITION_GENERATE
    assert entry.cascade_role is CascadeRole.TERMINAL
    assert entry.output is None
