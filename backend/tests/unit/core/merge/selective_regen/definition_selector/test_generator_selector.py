from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.timestamp import Timestamp
from infrahub.generators.models import ProposedChangeGeneratorDefinition

if TYPE_CHECKING:
    from infrahub.core.merge.selective_regen.definition_selector.generator_selector import GeneratorSelector
    from tests.helpers.selective_regen import RecordingGeneratorDiffCapturer

TARGET_BRANCH = "main"


def _generator_definition(name: str = "gen") -> ProposedChangeGeneratorDefinition:
    return ProposedChangeGeneratorDefinition(
        definition_id="def-1",
        definition_name=name,
        query_name="q",
        convert_query_response=False,
        class_name="C",
        file_path="gen.py",
        group_id="grp-1",
        parameters={},
        execute_in_proposed_change=False,
        execute_after_merge=True,
        query_id="q-1",
        query_models=["TestDevice"],
        query_payload="query {}",
        repository_id="repo-1",
    )


def test_build_request_threads_branch_definition_and_members(generator_selector: GeneratorSelector) -> None:
    definition = _generator_definition()

    request = generator_selector._build_request(
        definition=definition, target_branch=TARGET_BRANCH, members=["m1", "m2"]
    )

    assert request.branch == TARGET_BRANCH
    assert request.generator_definition is definition
    assert request.target_members == ["m1", "m2"]


async def test_output_capture_captures_the_runs_generators_by_name(
    generator_selector: GeneratorSelector, output_capturer: RecordingGeneratorDiffCapturer
) -> None:
    """output_capture derives the capture scope from each run's generator name, with no follow-up narrowing."""
    runs = [
        generator_selector._build_request(
            definition=_generator_definition(name="gen-a"), target_branch=TARGET_BRANCH, members=[]
        ),
        generator_selector._build_request(
            definition=_generator_definition(name="gen-b"), target_branch=TARGET_BRANCH, members=[]
        ),
    ]

    output = generator_selector.output_capture(runs)
    since = Timestamp()
    captured = await output.capture(since=since)

    assert output_capturer.calls == [(since, ["gen-a", "gen-b"])]
    assert captured is output_capturer.result


def test_consolidate_returns_the_runs_unchanged_for_a_source(generator_selector: GeneratorSelector) -> None:
    """A cascade source is not consolidated; its runs pass through the default unchanged."""
    runs = [
        generator_selector._build_request(definition=_generator_definition(), target_branch=TARGET_BRANCH, members=[])
    ]

    assert generator_selector.consolidate(runs) == runs


@dataclass
class RenderCase:
    name: str
    subscriber_id: str | None
    regenerate_all_members: bool
    impacted: list[str]
    expected: bool


RENDER_CASES = [
    RenderCase(
        name="new_instance_always_renders", subscriber_id=None, regenerate_all_members=False, impacted=[], expected=True
    ),
    RenderCase(
        name="regenerate_all_members_always_renders",
        subscriber_id="i1",
        regenerate_all_members=True,
        impacted=[],
        expected=True,
    ),
    RenderCase(
        name="existing_instance_renders_when_impacted",
        subscriber_id="i1",
        regenerate_all_members=False,
        impacted=["i1"],
        expected=True,
    ),
    RenderCase(
        name="existing_instance_skipped_when_not_impacted",
        subscriber_id="i1",
        regenerate_all_members=False,
        impacted=["i2"],
        expected=False,
    ),
]


@pytest.mark.parametrize("case", RENDER_CASES, ids=lambda case: case.name)
def test_should_render_instance_contract(case: RenderCase, generator_selector: GeneratorSelector) -> None:
    rendered = generator_selector._should_render(
        subscriber_id=case.subscriber_id, regenerate_all_members=case.regenerate_all_members, impacted=case.impacted
    )

    assert rendered is case.expected
