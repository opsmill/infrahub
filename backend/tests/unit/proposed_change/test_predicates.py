from __future__ import annotations

from dataclasses import dataclass

import pytest
from infrahub_sdk.diff import NodeDiff, NodeDiffElement

from infrahub.core.constants import InfrahubKind
from infrahub.message_bus.types import ProposedChangeArtifactDefinition
from infrahub.proposed_change.tasks import _definition_changed, _query_changed

QUERY_ID = "11111111-1111-1111-1111-111111111111"
DEFINITION_ID = "22222222-2222-2222-2222-222222222222"
OTHER_ID = "33333333-3333-3333-3333-333333333333"


def _build_definition(
    *,
    definition_id: str = DEFINITION_ID,
    query_id: str = QUERY_ID,
) -> ProposedChangeArtifactDefinition:
    return ProposedChangeArtifactDefinition(
        definition_id=definition_id,
        definition_name="artifact-def",
        artifact_name="device-config",
        query_name="GetNetworkDevice",
        query_id=query_id,
        query_models=["TestNetworkDevice"],
        query_payload="query { TestNetworkDevice { edges { node { id } } } }",
        repository_id="44444444-4444-4444-4444-444444444444",
        transform_kind=InfrahubKind.TRANSFORMJINJA2,
        template_path="device.j2",
        content_type="application/json",
        timeout=60,
    )


def _node_diff(
    *,
    node_id: str,
    kind: str = "CoreGraphQLQuery",
    action: str = "updated",
    elements: list[NodeDiffElement] | None = None,
) -> NodeDiff:
    return NodeDiff(
        branch="main",
        kind=kind,
        id=node_id,
        action=action,
        display_label="some-node",
        elements=elements if elements is not None else [],
    )


@dataclass(frozen=True, kw_only=True)
class QueryChangedCase:
    name: str
    diff: list[NodeDiff]
    expected: bool


QUERY_CHANGED_CASES: list[QueryChangedCase] = [
    QueryChangedCase(
        name="empty_diff_is_false",
        diff=[],
        expected=False,
    ),
    QueryChangedCase(
        name="updated_query_is_true",
        diff=[_node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery", action="updated")],
        expected=True,
    ),
    QueryChangedCase(
        name="added_query_is_true",
        diff=[_node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery", action="added")],
        expected=True,
    ),
    QueryChangedCase(
        name="unchanged_action_is_false",
        diff=[_node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery", action="unchanged")],
        expected=False,
    ),
    QueryChangedCase(
        name="removed_action_is_false",
        diff=[_node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery", action="removed")],
        expected=False,
    ),
    QueryChangedCase(
        name="mismatched_id_is_false",
        diff=[_node_diff(node_id=OTHER_ID, kind="CoreGraphQLQuery")],
        expected=False,
    ),
    QueryChangedCase(
        name="definition_id_alone_is_false",
        diff=[_node_diff(node_id=DEFINITION_ID, kind="CoreArtifactDefinition")],
        expected=False,
    ),
    QueryChangedCase(
        name="query_match_among_other_entries",
        diff=[
            _node_diff(node_id=OTHER_ID, kind="TestNetworkDevice"),
            _node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery"),
            _node_diff(node_id=DEFINITION_ID, kind="CoreArtifactDefinition"),
        ],
        expected=True,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in QUERY_CHANGED_CASES])
def test_query_changed(case: QueryChangedCase) -> None:
    """The predicate fires exactly when a node modification carries the query's id.

    The SDK inlines GraphQL fragment bodies into the stored ``query`` attribute
    of ``CoreGraphQLQuery`` before persisting, so any edit to a transitively
    referenced fragment surfaces as a modification of the same ``CoreGraphQLQuery``
    node. Selecting on the node id is therefore sufficient and avoids tracking
    fragment topology separately.

    Only ``added`` and ``updated`` actions trigger the predicate. ``unchanged``
    entries appear as parent context in enriched diffs and must not fire; ``removed``
    entries describe a deleted query that leaves the definition broken and offers
    nothing to regenerate against.
    """
    definition = _build_definition()
    assert _query_changed(definition=definition, diff_summary=case.diff) is case.expected


@dataclass(frozen=True, kw_only=True)
class DefinitionChangedCase:
    name: str
    diff: list[NodeDiff]
    expected: bool


DEFINITION_CHANGED_CASES: list[DefinitionChangedCase] = [
    DefinitionChangedCase(
        name="empty_diff_is_false",
        diff=[],
        expected=False,
    ),
    DefinitionChangedCase(
        name="mismatched_id_is_false",
        diff=[_node_diff(node_id=OTHER_ID, kind="CoreArtifactDefinition")],
        expected=False,
    ),
    DefinitionChangedCase(
        name="query_id_alone_is_false",
        diff=[_node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery")],
        expected=False,
    ),
    DefinitionChangedCase(
        name="updated_definition_is_true",
        diff=[_node_diff(node_id=DEFINITION_ID, kind="CoreArtifactDefinition", action="updated")],
        expected=True,
    ),
    DefinitionChangedCase(
        name="added_definition_is_true",
        diff=[_node_diff(node_id=DEFINITION_ID, kind="CoreArtifactDefinition", action="added")],
        expected=True,
    ),
    DefinitionChangedCase(
        name="unchanged_action_is_false",
        diff=[_node_diff(node_id=DEFINITION_ID, kind="CoreArtifactDefinition", action="unchanged")],
        expected=False,
    ),
    DefinitionChangedCase(
        name="removed_action_is_false",
        diff=[_node_diff(node_id=DEFINITION_ID, kind="CoreArtifactDefinition", action="removed")],
        expected=False,
    ),
    DefinitionChangedCase(
        name="definition_match_among_other_entries",
        diff=[
            _node_diff(node_id=OTHER_ID, kind="TestNetworkDevice"),
            _node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery"),
            _node_diff(node_id=DEFINITION_ID, kind="CoreArtifactDefinition"),
        ],
        expected=True,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in DEFINITION_CHANGED_CASES])
def test_definition_changed(case: DefinitionChangedCase) -> None:
    """The predicate fires exactly when the definition node itself is modified.

    Any attribute change or relationship repoint on ``CoreArtifactDefinition``
    surfaces as a modification of the definition's own node id in the diff
    summary, so a single id-based check covers every shape of definition-level
    change uniformly.

    Only ``added`` and ``updated`` actions trigger the predicate. ``unchanged``
    entries appear as parent context in enriched diffs and must not fire;
    ``removed`` definitions cannot reach this predicate because the artifact
    definition list is sourced from the source branch's current state.
    """
    definition = _build_definition()
    assert _definition_changed(definition=definition, diff_summary=case.diff) is case.expected
