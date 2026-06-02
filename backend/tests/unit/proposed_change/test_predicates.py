from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from infrahub_sdk.diff import NodeDiff, NodeDiffElement

from infrahub.core.constants import InfrahubKind
from infrahub.message_bus.types import ProposedChangeArtifactDefinition, ProposedChangeRepository
from infrahub.proposed_change.tasks import _definition_changed, _query_changed, _transform_changed

QUERY_ID = "11111111-1111-1111-1111-111111111111"
DEFINITION_ID = "22222222-2222-2222-2222-222222222222"
OTHER_ID = "33333333-3333-3333-3333-333333333333"


def _build_definition(
    *,
    definition_id: str = DEFINITION_ID,
    query_id: str = QUERY_ID,
    dependencies: list[str] | None = None,
    dependencies_complete: bool | None = None,
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
        dependencies=dependencies,
        dependencies_complete=dependencies_complete,
    )


def _build_repo_diff(
    *,
    files_added: list[str] | None = None,
    files_changed: list[str] | None = None,
    files_removed: list[str] | None = None,
) -> ProposedChangeRepository:
    return ProposedChangeRepository(
        repository_id="44444444-4444-4444-4444-444444444444",
        repository_name="test-repo",
        read_only=False,
        source_branch="feature",
        destination_branch="main",
        internal_status="active",
        files_added=files_added or [],
        files_changed=files_changed or [],
        files_removed=files_removed or [],
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


@dataclass(frozen=True, kw_only=True)
class TransformChangedCase:
    name: str
    dependencies: list[str] | None
    dependencies_complete: bool | None
    files_added: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    files_removed: list[str] = field(default_factory=list)
    expected: bool


TRANSFORM_CHANGED_CASES: list[TransformChangedCase] = [
    TransformChangedCase(
        name="null_null_with_no_file_changes_is_false",
        dependencies=None,
        dependencies_complete=None,
        expected=False,
    ),
    TransformChangedCase(
        name="null_null_with_any_file_change_is_true",
        dependencies=None,
        dependencies_complete=None,
        files_changed=["any/path.txt"],
        expected=True,
    ),
    TransformChangedCase(
        name="incomplete_closure_with_no_file_changes_is_false",
        dependencies=["templates/device.j2"],
        dependencies_complete=False,
        expected=False,
    ),
    TransformChangedCase(
        name="incomplete_closure_with_any_file_change_is_true",
        dependencies=["templates/device.j2"],
        dependencies_complete=False,
        files_added=["unrelated/file.md"],
        expected=True,
    ),
    TransformChangedCase(
        name="empty_closure_true_complete_is_always_false",
        dependencies=[],
        dependencies_complete=True,
        files_added=["a.txt"],
        files_changed=["b.txt"],
        files_removed=["c.txt"],
        expected=False,
    ),
    TransformChangedCase(
        name="non_empty_closure_no_intersection_is_false",
        dependencies=["templates/device.j2", ".infrahub.yml"],
        dependencies_complete=True,
        files_changed=["transforms/other/main.py"],
        expected=False,
    ),
    TransformChangedCase(
        name="non_empty_closure_with_intersection_in_added_is_true",
        dependencies=["templates/device.j2", ".infrahub.yml"],
        dependencies_complete=True,
        files_added=["templates/device.j2"],
        expected=True,
    ),
    TransformChangedCase(
        name="non_empty_closure_with_intersection_in_changed_is_true",
        dependencies=["templates/device.j2", ".infrahub.yml"],
        dependencies_complete=True,
        files_changed=[".infrahub.yml"],
        expected=True,
    ),
    TransformChangedCase(
        name="non_empty_closure_with_intersection_in_removed_is_true",
        dependencies=["templates/device.j2", ".infrahub.yml"],
        dependencies_complete=True,
        files_removed=["templates/device.j2"],
        expected=True,
    ),
    TransformChangedCase(
        name="canonicalizer_applied_symmetrically_to_diff_side",
        dependencies=["templates/device.j2"],
        dependencies_complete=True,
        files_changed=["./templates/device.j2"],
        expected=True,
    ),
    TransformChangedCase(
        name="canonicalizer_applied_symmetrically_to_windows_diff_paths",
        dependencies=["templates/device.j2"],
        dependencies_complete=True,
        files_changed=["templates\\device.j2"],
        expected=True,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in TRANSFORM_CHANGED_CASES])
def test_transform_changed(case: TransformChangedCase) -> None:
    """The predicate's four behavior branches cover the full closure/completeness/diff matrix.

    The closure-trust state space is small but each branch carries different
    pipeline semantics: null/null and any-False fall back to the legacy
    file-change gate; empty-True returns no regeneration regardless of
    diff content; non-empty-True is a canonicalized set intersection.
    """
    definition = _build_definition(
        dependencies=case.dependencies,
        dependencies_complete=case.dependencies_complete,
    )
    repo_diff = _build_repo_diff(
        files_added=case.files_added,
        files_changed=case.files_changed,
        files_removed=case.files_removed,
    )
    assert _transform_changed(definition=definition, repo_diff=repo_diff) is case.expected
