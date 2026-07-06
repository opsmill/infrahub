from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from infrahub_sdk.diff import NodeDiff, NodeDiffElement

from infrahub.generators.models import ProposedChangeGeneratorDefinition
from infrahub.message_bus.types import ProposedChangeRepository
from infrahub.proposed_change.tasks import _definition_changed, _query_changed, _run_generator, _transform_changed

QUERY_ID = "11111111-1111-1111-1111-111111111111"
DEFINITION_ID = "22222222-2222-2222-2222-222222222222"
OTHER_ID = "33333333-3333-3333-3333-333333333333"
REPOSITORY_ID = "44444444-4444-4444-4444-444444444444"

# The package-directory floor a generator's closure carries: every sibling under its directory plus
# the repository manifest. A file edit anywhere in the floor must select the generator.
PACKAGE_FLOOR = [
    ".infrahub.yml",
    "generators/a/__init__.py",
    "generators/a/a.py",
    "generators/a/helpers.py",
]


def _build_definition(
    *,
    definition_id: str = DEFINITION_ID,
    query_id: str = QUERY_ID,
    dependencies: list[str] | None = None,
    dependencies_complete: bool | None = None,
) -> ProposedChangeGeneratorDefinition:
    return ProposedChangeGeneratorDefinition(
        definition_id=definition_id,
        definition_name="device-generator",
        query_name="GetNetworkDevice",
        query_id=query_id,
        query_models=["TestNetworkDevice"],
        query_payload="query { TestNetworkDevice { edges { node { id } } } }",
        repository_id=REPOSITORY_ID,
        class_name="DeviceGenerator",
        file_path="generators/a/a.py",
        group_id="55555555-5555-5555-5555-555555555555",
        parameters={"name": "name__value"},
        convert_query_response=False,
        execute_in_proposed_change=True,
        execute_after_merge=True,
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
        repository_id=REPOSITORY_ID,
        repository_name="generator-repo",
        read_only=False,
        source_branch="feature",
        destination_branch="main",
        internal_status="active",
        files_added=files_added or [],
        files_changed=files_changed or [],
        files_removed=files_removed or [],
    )


def _node_diff(*, node_id: str, kind: str = "CoreGraphQLQuery", action: str = "UPDATED") -> NodeDiff:
    # ``action`` is the uppercase GraphQL enum name as emitted by the diff summary, not the lowercase
    # ``DiffAction.*.value``; fixtures must mirror production casing so the case-insensitive match is exercised.
    elements: list[NodeDiffElement] = []
    return NodeDiff(
        branch="main",
        kind=kind,
        id=node_id,
        action=action,
        display_label="some-node",
        elements=elements,
    )


@dataclass(frozen=True, kw_only=True)
class QueryChangedCase:
    name: str
    diff: list[NodeDiff]
    expected: bool


QUERY_CHANGED_CASES: list[QueryChangedCase] = [
    QueryChangedCase(name="empty_diff_is_false", diff=[], expected=False),
    QueryChangedCase(
        name="query_id_match_is_true",
        diff=[_node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery")],
        expected=True,
    ),
    QueryChangedCase(
        name="unresolvable_query_peer_never_matches_here",
        diff=[_node_diff(node_id=OTHER_ID, kind="CoreGraphQLQuery")],
        expected=False,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in QUERY_CHANGED_CASES])
def test_query_changed_generator_variant(case: QueryChangedCase) -> None:
    """The query predicate fires for a generator definition exactly when its query node id is modified.

    A generator whose query peer cannot be resolved (no diff entry carries its id) never matches here;
    the other signals still cover it, so the never-under-run invariant is preserved by composition.
    """
    definition = _build_definition()
    assert _query_changed(definition=definition, diff_summary=case.diff).matched is case.expected


@dataclass(frozen=True, kw_only=True)
class DefinitionChangedCase:
    name: str
    diff: list[NodeDiff]
    expected: bool


DEFINITION_CHANGED_CASES: list[DefinitionChangedCase] = [
    DefinitionChangedCase(name="empty_diff_is_false", diff=[], expected=False),
    DefinitionChangedCase(
        name="definition_id_match_is_true",
        diff=[_node_diff(node_id=DEFINITION_ID, kind="CoreGeneratorDefinition")],
        expected=True,
    ),
    DefinitionChangedCase(
        name="query_id_alone_is_false",
        diff=[_node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery")],
        expected=False,
    ),
    DefinitionChangedCase(
        name="definition_match_among_other_entries",
        diff=[
            _node_diff(node_id=OTHER_ID, kind="TestNetworkDevice"),
            _node_diff(node_id=DEFINITION_ID, kind="CoreGeneratorDefinition"),
        ],
        expected=True,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in DEFINITION_CHANGED_CASES])
def test_definition_changed_generator_variant(case: DefinitionChangedCase) -> None:
    """The definition predicate fires for a generator definition when its own node id is modified.

    An attribute change or a ``targets`` repoint on the definition surfaces as a modification of the
    definition's own node id, so a single id-based check covers every shape of definition-level change.
    """
    definition = _build_definition()
    assert _definition_changed(definition=definition, diff_summary=case.diff).matched is case.expected


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
        name="complete_closure_unrelated_file_is_false",
        dependencies=PACKAGE_FLOOR,
        dependencies_complete=True,
        files_changed=["generators/b/b.py"],
        expected=False,
    ),
    TransformChangedCase(
        name="source_file_inside_floor_is_true",
        dependencies=PACKAGE_FLOOR,
        dependencies_complete=True,
        files_changed=["generators/a/a.py"],
        expected=True,
    ),
    TransformChangedCase(
        name="sibling_module_in_same_package_is_true",
        dependencies=PACKAGE_FLOOR,
        dependencies_complete=True,
        files_changed=["generators/a/helpers.py"],
        expected=True,
    ),
    TransformChangedCase(
        name="legacy_null_dependencies_falls_back_to_any_file_change",
        dependencies=None,
        dependencies_complete=None,
        files_changed=["anything/at/all.py"],
        expected=True,
    ),
    TransformChangedCase(
        name="incomplete_closure_falls_back_to_any_file_change",
        dependencies=PACKAGE_FLOOR,
        dependencies_complete=False,
        files_changed=["unrelated/file.md"],
        expected=True,
    ),
    TransformChangedCase(
        name="legacy_null_dependencies_with_no_modifications_is_false",
        dependencies=None,
        dependencies_complete=None,
        expected=False,
    ),
    TransformChangedCase(
        name="incomplete_closure_with_no_modifications_is_false",
        dependencies=PACKAGE_FLOOR,
        dependencies_complete=False,
        expected=False,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in TRANSFORM_CHANGED_CASES])
def test_transform_changed_generator_variant(case: TransformChangedCase) -> None:
    """The closure predicate intersects a generator's package floor with the repo diff.

    A file edit anywhere in the package-directory floor - the source module or a sibling it never
    imports - selects the generator, while an unrelated file does not. The legacy (``dependencies=null``)
    and incomplete (``dependencies_complete=False``) states fall back to regenerate-on-any-file-change so
    a generator is never under-run.
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
    assert _transform_changed(definition=definition, repo_diff=repo_diff).matched is case.expected


@dataclass(frozen=True, kw_only=True)
class RunGeneratorCase:
    name: str
    instance_id: str | None
    managed_branch: bool
    impacted_instances: list[str]
    expected: bool


RUN_GENERATOR_CASES: list[RunGeneratorCase] = [
    RunGeneratorCase(
        name="new_member_runs_regardless_of_managed_branch",
        instance_id=None,
        managed_branch=False,
        impacted_instances=[],
        expected=True,
    ),
    RunGeneratorCase(
        name="data_changed_instance_runs_regardless_of_managed_branch",
        instance_id="instance-1",
        managed_branch=False,
        impacted_instances=["instance-1"],
        expected=True,
    ),
    RunGeneratorCase(
        name="closure_changed_managed_branch_runs_every_existing_instance",
        instance_id="instance-1",
        managed_branch=True,
        impacted_instances=[],
        expected=True,
    ),
    RunGeneratorCase(
        name="nothing_relevant_changed_existing_instance_is_skipped",
        instance_id="instance-1",
        managed_branch=False,
        impacted_instances=["instance-other"],
        expected=False,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in RUN_GENERATOR_CASES])
def test_run_generator_never_under_runs(case: RunGeneratorCase) -> None:
    """After the per-member gate swap the three always-run categories are still honored.

    A new member (no prior instance) and an instance whose data changed both run regardless of the
    closure-derived ``managed_branch``; a closure/query/definition change sets ``managed_branch`` and
    runs every existing instance; only an existing instance with nothing relevant changed is skipped.
    """
    assert (
        _run_generator(
            instance_id=case.instance_id,
            managed_branch=case.managed_branch,
            impacted_instances=case.impacted_instances,
        )
        is case.expected
    )


def test_legacy_generator_forces_managed_branch_on_any_file_change() -> None:
    """A legacy generator (``dependencies=null``) computes ``managed_branch=True`` on any file change.

    This is the gate-level guarantee behind never-under-run: a pre-feature generator whose closure was
    never built falls back to the file-change signal, so every existing instance re-runs on any commit.
    """
    definition = _build_definition(dependencies=None, dependencies_complete=None)
    repo_diff = _build_repo_diff(files_changed=["generators/a/a.py"])

    managed_branch = (
        _query_changed(definition=definition, diff_summary=[]).matched
        or _definition_changed(definition=definition, diff_summary=[]).matched
        or _transform_changed(definition=definition, repo_diff=repo_diff).matched
    )

    assert managed_branch is True
