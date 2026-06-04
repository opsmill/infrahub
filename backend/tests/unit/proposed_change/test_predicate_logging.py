from __future__ import annotations

from infrahub_sdk.diff import NodeDiff, NodeDiffElement, NodeDiffSummary

from infrahub.core.constants import InfrahubKind
from infrahub.message_bus.types import ProposedChangeArtifactDefinition, ProposedChangeRepository
from infrahub.proposed_change.tasks import _definition_changed, _query_changed, _transform_changed

QUERY_ID = "11111111-1111-1111-1111-111111111111"
DEFINITION_ID = "22222222-2222-2222-2222-222222222222"


def _build_definition(
    *,
    dependencies: list[str] | None = None,
    dependencies_complete: bool | None = None,
) -> ProposedChangeArtifactDefinition:
    return ProposedChangeArtifactDefinition(
        definition_id=DEFINITION_ID,
        definition_name="artifact-def",
        artifact_name="device-config",
        query_name="GetNetworkDevice",
        query_id=QUERY_ID,
        query_models=["TestNetworkDevice"],
        query_payload="query GetNetworkDevice { TestNetworkDevice { edges { node { name { value } } } } }",
        repository_id="44444444-4444-4444-4444-444444444444",
        transform_kind=InfrahubKind.TRANSFORMJINJA2,
        template_path="templates/device.j2",
        content_type="application/json",
        timeout=60,
        dependencies=dependencies,
        dependencies_complete=dependencies_complete,
    )


def _build_repo_diff(*, files_changed: list[str] | None = None) -> ProposedChangeRepository:
    return ProposedChangeRepository(
        repository_id="44444444-4444-4444-4444-444444444444",
        repository_name="test-repo",
        read_only=False,
        source_branch="feature",
        destination_branch="main",
        internal_status="active",
        files_changed=files_changed or [],
    )


def _node_diff(*, node_id: str, kind: str, element_names: list[str] | None = None) -> NodeDiff:
    return NodeDiff(
        branch="main",
        kind=kind,
        id=node_id,
        action="updated",
        display_label="some-node",
        elements=[
            NodeDiffElement(
                name=name,
                element_type="attribute",
                action="updated",
                summary=NodeDiffSummary(added=0, updated=1, removed=0),
            )
            for name in (element_names or [])
        ],
    )


def test_query_changed_reason_names_the_query() -> None:
    """A firing query predicate carries a reason naming the query so the gate can explain the regeneration.

    The reason is the user-facing answer to "why did these artifacts regenerate?";
    it identifies the query by name and id without forcing a diff lookup.
    """
    outcome = _query_changed(
        definition=_build_definition(),
        diff_summary=[_node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery")],
    )

    assert outcome.matched is True
    assert outcome.reason == (
        f"Definition artifact-def ({DEFINITION_ID}): GraphQL query GetNetworkDevice ({QUERY_ID}) was modified - "
        f"all artifacts of this definition will regenerate."
    )


def test_query_changed_carries_no_reason_when_it_does_not_fire() -> None:
    """A predicate that does not match carries no reason so the gate emits nothing for it."""
    outcome = _query_changed(definition=_build_definition(), diff_summary=[])

    assert outcome.matched is False
    assert outcome.reason is None


def test_definition_changed_reason_names_the_changed_fields() -> None:
    """A firing definition predicate names the attributes or relationships that changed.

    The changed-field list is read straight from the matching diff entry so the
    reader can see exactly which definition-level edit (e.g. a ``targets`` repoint)
    drove the regeneration.
    """
    outcome = _definition_changed(
        definition=_build_definition(),
        diff_summary=[_node_diff(node_id=DEFINITION_ID, kind="CoreArtifactDefinition", element_names=["targets"])],
    )

    assert outcome.matched is True
    assert outcome.reason == (
        f"Definition artifact-def ({DEFINITION_ID}): definition node was modified (targets) - "
        f"all artifacts of this definition will regenerate."
    )


def test_definition_changed_reason_falls_back_to_generic_detail_without_field_detail() -> None:
    """When the matching entry carries no per-field detail, the reason still records the definition-level change."""
    outcome = _definition_changed(
        definition=_build_definition(),
        diff_summary=[_node_diff(node_id=DEFINITION_ID, kind="CoreArtifactDefinition")],
    )

    assert outcome.matched is True
    assert outcome.reason == (
        f"Definition artifact-def ({DEFINITION_ID}): definition node was modified - "
        f"all artifacts of this definition will regenerate."
    )


def test_transform_changed_reason_names_the_intersecting_file() -> None:
    """The precise-closure path names the file whose change is inside the transform's dependency closure."""
    outcome = _transform_changed(
        definition=_build_definition(dependencies=["templates/device.j2"], dependencies_complete=True),
        repo_diff=_build_repo_diff(files_changed=["templates/device.j2"]),
    )

    assert outcome.matched is True
    assert outcome.reason == (
        "Definition artifact-def: file templates/device.j2 changed and is in this transform's "
        "dependency closure - all artifacts will regenerate."
    )


def test_transform_changed_reason_explains_the_legacy_fallback() -> None:
    """A pre-feature node (dependencies=null) explains that it self-heals on its next re-import.

    This is the upgrade-safety message: it tells an operator the transform is on the
    legacy gate by necessity, not by mistake, and how it leaves that state.
    """
    outcome = _transform_changed(
        definition=_build_definition(dependencies=None, dependencies_complete=None),
        repo_diff=_build_repo_diff(files_changed=["any/path.txt"]),
    )

    assert outcome.matched is True
    assert outcome.reason == (
        "Definition artifact-def: transform was imported before this feature deployed (dependencies=null) - "
        "falling back to regenerate-on-any-file-change. The next re-import of this transform will populate "
        "its dependency closure."
    )


def test_transform_changed_reason_explains_the_incomplete_closure_fallback() -> None:
    """An incomplete closure (dependencies_complete=False) explains the safety fallback to regenerate-on-any-change."""
    outcome = _transform_changed(
        definition=_build_definition(dependencies=["templates/device.j2"], dependencies_complete=False),
        repo_diff=_build_repo_diff(files_changed=["unrelated/file.md"]),
    )

    assert outcome.matched is True
    assert outcome.reason == (
        "Definition artifact-def: transform dependency closure is incomplete (dependencies_complete=False) - "
        "falling back to regenerate-on-any-file-change."
    )


def test_transform_changed_carries_no_reason_on_a_no_op_complete_closure() -> None:
    """A complete closure that no file change intersects carries no reason and does not match."""
    outcome = _transform_changed(
        definition=_build_definition(dependencies=["templates/device.j2"], dependencies_complete=True),
        repo_diff=_build_repo_diff(files_changed=["transforms/other/main.py"]),
    )

    assert outcome.matched is False
    assert outcome.reason is None
