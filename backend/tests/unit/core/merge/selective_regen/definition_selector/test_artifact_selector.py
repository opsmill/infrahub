from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.message_bus.types import ProposedChangeArtifactDefinition

if TYPE_CHECKING:
    from infrahub.core.merge.selective_regen.definition_selector.artifact_selector import ArtifactSelector

TARGET_BRANCH = "main"


def _artifact_definition() -> ProposedChangeArtifactDefinition:
    return ProposedChangeArtifactDefinition(
        definition_id="def-1",
        definition_name="art",
        artifact_name="artifact",
        query_name="q",
        query_id="q-1",
        query_models=["TestDevice"],
        query_payload="query {}",
        repository_id="repo-1",
        transform_kind="CoreTransformJinja2",
        content_type="text/plain",
        timeout=10,
    )


def test_build_request_carries_definition_identity_and_members(artifact_selector: ArtifactSelector) -> None:
    definition = _artifact_definition()

    request = artifact_selector._build_request(definition=definition, target_branch=TARGET_BRANCH, members=["m1", "m2"])

    assert request.branch == TARGET_BRANCH
    assert request.artifact_definition_id == "def-1"
    assert request.artifact_definition_name == "art"
    assert request.members == ["m1", "m2"]


@dataclass
class RenderCase:
    name: str
    subscriber_id: str | None
    regenerate_all_members: bool
    impacted: list[str]
    expected: bool


RENDER_CASES = [
    RenderCase(
        name="new_artifact_always_renders", subscriber_id=None, regenerate_all_members=False, impacted=[], expected=True
    ),
    RenderCase(
        name="regenerate_all_members_always_renders",
        subscriber_id="a1",
        regenerate_all_members=True,
        impacted=[],
        expected=True,
    ),
    RenderCase(
        name="existing_artifact_renders_when_impacted",
        subscriber_id="a1",
        regenerate_all_members=False,
        impacted=["a1"],
        expected=True,
    ),
    RenderCase(
        name="existing_artifact_skipped_when_not_impacted",
        subscriber_id="a1",
        regenerate_all_members=False,
        impacted=["a2"],
        expected=False,
    ),
]


@pytest.mark.parametrize("case", RENDER_CASES, ids=lambda case: case.name)
def test_should_render_artifact_contract(case: RenderCase, artifact_selector: ArtifactSelector) -> None:
    rendered = artifact_selector._should_render(
        subscriber_id=case.subscriber_id, regenerate_all_members=case.regenerate_all_members, impacted=case.impacted
    )

    assert rendered is case.expected
