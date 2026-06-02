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
        name="matching_query_id_is_true",
        diff=[_node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery")],
        expected=True,
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
    QueryChangedCase(
        name="fragment_edit_surfaces_as_query_node_modification",
        diff=[
            _node_diff(
                node_id=QUERY_ID,
                kind="CoreGraphQLQuery",
                action="updated",
                elements=[
                    NodeDiffElement(
                        action="updated",
                        element_type="ATTRIBUTE",
                        name="query",
                        summary={"added": 0, "updated": 1, "removed": 0},
                    )
                ],
            ),
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
        name="attribute_change_on_definition",
        diff=[
            _node_diff(
                node_id=DEFINITION_ID,
                kind="CoreArtifactDefinition",
                action="updated",
                elements=[
                    NodeDiffElement(
                        action="updated",
                        element_type="ATTRIBUTE",
                        name="artifact_name",
                        summary={"added": 0, "updated": 1, "removed": 0},
                    )
                ],
            ),
        ],
        expected=True,
    ),
    DefinitionChangedCase(
        name="targets_relationship_repoint",
        diff=[
            _node_diff(
                node_id=DEFINITION_ID,
                kind="CoreArtifactDefinition",
                action="updated",
                elements=[
                    NodeDiffElement(
                        action="updated",
                        element_type="RELATIONSHIP_ONE",
                        name="targets",
                        summary={"added": 1, "updated": 0, "removed": 1},
                    )
                ],
            ),
        ],
        expected=True,
    ),
    DefinitionChangedCase(
        name="transformation_relationship_repoint",
        diff=[
            _node_diff(
                node_id=DEFINITION_ID,
                kind="CoreArtifactDefinition",
                action="updated",
                elements=[
                    NodeDiffElement(
                        action="updated",
                        element_type="RELATIONSHIP_ONE",
                        name="transformation",
                        summary={"added": 1, "updated": 0, "removed": 1},
                    )
                ],
            ),
        ],
        expected=True,
    ),
    DefinitionChangedCase(
        name="query_relationship_repoint",
        diff=[
            _node_diff(
                node_id=DEFINITION_ID,
                kind="CoreArtifactDefinition",
                action="updated",
                elements=[
                    NodeDiffElement(
                        action="updated",
                        element_type="RELATIONSHIP_ONE",
                        name="query",
                        summary={"added": 1, "updated": 0, "removed": 1},
                    )
                ],
            ),
        ],
        expected=True,
    ),
    DefinitionChangedCase(
        name="definition_added",
        diff=[
            _node_diff(
                node_id=DEFINITION_ID,
                kind="CoreArtifactDefinition",
                action="added",
            ),
        ],
        expected=True,
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

    Any attribute change on ``CoreArtifactDefinition``, or any repoint of one of
    its relationships (``targets``, ``transformation``, ``query``), surfaces as
    a modification of the definition's own node id in the diff summary. A single
    id-based check therefore covers every shape of definition-level change
    uniformly, without enumerating attribute names.
    """
    definition = _build_definition()
    assert _definition_changed(definition=definition, diff_summary=case.diff) is case.expected
