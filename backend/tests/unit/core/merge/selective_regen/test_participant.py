from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.merge.selective_regen.models import CascadeRole
from infrahub.core.merge.selective_regen.participant import CascadeSource, CascadeTerminal
from infrahub.generators.models import RequestGeneratorDefinitionRun
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE, REQUEST_GENERATOR_DEFINITION_RUN
from tests.helpers.selective_regen import ArtifactForcingSelector, GeneratorForcingSelector, StubCascadeSourceOutput

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.merge.selective_regen.models import CascadeSourceOutput, RegenerationRequest


class _RecordingOutputFactory:
    """A CascadeSourceOutputFactory that records the requests it was asked to build the capture from."""

    def __init__(self) -> None:
        self.seen: list[Sequence[RegenerationRequest]] = []
        self.result = StubCascadeSourceOutput()

    def for_requests(self, requests: Sequence[RegenerationRequest]) -> CascadeSourceOutput:
        self.seen.append(requests)
        return self.result


def test_source_entry_forwards_its_requests_and_carries_the_built_output() -> None:
    """A source's entry is tagged SOURCE and carries the capture its output builds from those requests."""
    output = _RecordingOutputFactory()
    selector = GeneratorForcingSelector(definitions=[], member_ids=[], subscriber_by_member={})
    participant = CascadeSource[RequestGeneratorDefinitionRun](selector, output=output)
    requests: list[RequestGeneratorDefinitionRun] = []

    entry = participant.to_entry(requests)

    assert participant.role is CascadeRole.SOURCE
    assert entry.workflow is REQUEST_GENERATOR_DEFINITION_RUN
    assert entry.cascade_role is CascadeRole.SOURCE
    assert entry.requests is requests
    assert output.seen[0] is requests
    assert entry.output is output.result


def test_terminal_entry_carries_no_output() -> None:
    """A terminal's entry is tagged TERMINAL and carries no output, since nothing reselects from it."""
    selector = ArtifactForcingSelector(definitions=[], member_ids=[], subscriber_by_member={})
    participant = CascadeTerminal(selector)

    entry = participant.to_entry([])

    assert participant.role is CascadeRole.TERMINAL
    assert entry.workflow is REQUEST_ARTIFACT_DEFINITION_GENERATE
    assert entry.cascade_role is CascadeRole.TERMINAL
    assert entry.output is None
