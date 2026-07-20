from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pytest
from infrahub_sdk.diff import NodeDiff

from infrahub.core.merge.selective_regen.gate import DefinitionGate
from infrahub.core.merge.selective_regen.models import GateResult
from infrahub.generators.models import ProposedChangeGeneratorDefinition
from infrahub.message_bus.types import ProposedChangeArtifactDefinition

TARGET_BRANCH = "main"
DEFINITION_ID = "definition-1"
QUERY_ID = "query-1"
GROUP_ID = "group-1"


def _node_diff(*, node_id: str) -> NodeDiff:
    return NodeDiff(
        branch=TARGET_BRANCH, kind="TestDevice", id=node_id, action="UPDATED", display_label="node", elements=[]
    )


def _generator_definition(*, query_models: list[str]) -> ProposedChangeGeneratorDefinition:
    return ProposedChangeGeneratorDefinition(
        definition_id=DEFINITION_ID,
        definition_name="gen-def",
        query_name="gen-query",
        query_id=QUERY_ID,
        query_models=query_models,
        query_payload="query { TestDevice { edges { node { id } } } }",
        repository_id="repo-1",
        convert_query_response=False,
        class_name="MyGenerator",
        file_path="generators/my_generator.py",
        group_id=GROUP_ID,
        parameters={},
        execute_in_proposed_change=True,
        execute_after_merge=True,
    )


def _artifact_definition(*, query_models: list[str]) -> ProposedChangeArtifactDefinition:
    return ProposedChangeArtifactDefinition(
        definition_id=DEFINITION_ID,
        definition_name="art-def",
        artifact_name="my-artifact",
        query_name="art-query",
        query_id=QUERY_ID,
        query_models=query_models,
        query_payload="query { TestDevice { edges { node { id } } } }",
        repository_id="repo-1",
        transform_kind="CoreTransformJinja2",
        content_type="text/plain",
        timeout=30,
    )


@dataclass(frozen=True, kw_only=True)
class GateCase:
    name: str
    is_artifact: bool = False
    query_models: list[str] = field(default_factory=lambda: ["TestDevice"])
    modified_kinds: list[str] = field(default_factory=list)
    diff_node_ids: list[str] = field(default_factory=list)
    expected: GateResult


GATE_CASES = [
    GateCase(
        name="no_signal_is_not_selected",
        expected=GateResult(regenerate_all_members=False, selected=False),
    ),
    GateCase(
        name="query_change_manages_whole_branch",
        diff_node_ids=[QUERY_ID],
        expected=GateResult(regenerate_all_members=True, selected=True),
    ),
    GateCase(
        name="definition_change_manages_whole_branch",
        diff_node_ids=[DEFINITION_ID],
        expected=GateResult(regenerate_all_members=True, selected=True),
    ),
    GateCase(
        name="modified_kind_selects_without_managing_branch",
        modified_kinds=["TestDevice"],
        expected=GateResult(regenerate_all_members=False, selected=True),
    ),
    GateCase(
        name="group_membership_selects_without_managing_branch",
        diff_node_ids=[GROUP_ID],
        expected=GateResult(regenerate_all_members=False, selected=True),
    ),
    GateCase(
        name="unrelated_node_in_diff_is_not_selected",
        diff_node_ids=["unrelated-node"],
        expected=GateResult(regenerate_all_members=False, selected=False),
    ),
    GateCase(
        name="artifact_matches_profile_stripped_kind",
        is_artifact=True,
        modified_kinds=["ProfileTestDevice"],
        expected=GateResult(regenerate_all_members=False, selected=True),
    ),
    GateCase(
        name="generator_ignores_profile_stripped_kind",
        is_artifact=False,
        modified_kinds=["ProfileTestDevice"],
        expected=GateResult(regenerate_all_members=False, selected=False),
    ),
]


@pytest.mark.parametrize("case", GATE_CASES, ids=lambda case: case.name)
def test_definition_gate_evaluate(case: GateCase) -> None:
    definition = (
        _artifact_definition(query_models=case.query_models)
        if case.is_artifact
        else _generator_definition(query_models=case.query_models)
    )
    gate = DefinitionGate(log=logging.getLogger("test_definition_gate"))

    result = gate.evaluate(
        definition=definition,
        diff_summary=[_node_diff(node_id=node_id) for node_id in case.diff_node_ids],
        modified_kinds=case.modified_kinds,
        group_id=GROUP_ID,
    )

    assert result == case.expected
