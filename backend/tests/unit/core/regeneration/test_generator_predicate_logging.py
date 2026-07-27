from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.regeneration.models import RegenerationReason
from infrahub.core.regeneration.predicates import definition_changed, query_changed, transform_changed
from infrahub.generators.models import ProposedChangeGeneratorDefinition
from infrahub.message_bus.types import ProposedChangeRepository
from tests.helpers.diff_summary import node_diff

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

QUERY_ID = "11111111-1111-1111-1111-111111111111"
DEFINITION_ID = "22222222-2222-2222-2222-222222222222"
REPOSITORY_ID = "44444444-4444-4444-4444-444444444444"


def _build_definition(
    *,
    dependencies: list[str] | None = None,
    dependencies_complete: bool | None = None,
) -> ProposedChangeGeneratorDefinition:
    return ProposedChangeGeneratorDefinition(
        definition_id=DEFINITION_ID,
        definition_name="device-generator",
        query_name="GetNetworkDevice",
        query_id=QUERY_ID,
        query_models=["TestNetworkDevice"],
        query_payload="query GetNetworkDevice { TestNetworkDevice { edges { node { name { value } } } } }",
        repository_id=REPOSITORY_ID,
        class_name="DeviceGenerator",
        file_path="generators/device/device.py",
        group_id="55555555-5555-5555-5555-555555555555",
        parameters={"name": "name__value"},
        convert_query_response=False,
        execute_in_proposed_change=True,
        execute_after_merge=True,
        dependencies=dependencies,
        dependencies_complete=dependencies_complete,
    )


def _build_repo_diff(*, files_changed: list[str] | None = None) -> ProposedChangeRepository:
    return ProposedChangeRepository(
        repository_id=REPOSITORY_ID,
        repository_name="generator-repo",
        read_only=False,
        source_branch="feature",
        destination_branch="main",
        internal_status="active",
        files_changed=files_changed or [],
    )


def _node_diff(*, node_id: str, kind: str, element_names: list[str] | None = None) -> NodeDiff:
    return node_diff(node_id=node_id, kind=kind, display_label="some-node", field_names=element_names)


def test_query_changed_reason_uses_generator_nouns() -> None:
    """A firing query predicate names the query and uses the generator-correct ``instances`` noun."""
    outcome = query_changed(
        definition=_build_definition(),
        diff_summary=[_node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery")],
    )

    assert outcome.matched is True
    assert outcome.trigger is not None
    assert outcome.trigger.code is RegenerationReason.QUERY_CHANGED
    assert outcome.reason == (
        f"Definition device-generator ({DEFINITION_ID}): GraphQL query GetNetworkDevice ({QUERY_ID}) was modified - "
        f"all instances of this definition will regenerate."
    )


def test_definition_changed_reason_uses_generator_nouns() -> None:
    """A firing definition predicate names the changed fields and uses the ``instances`` noun."""
    outcome = definition_changed(
        definition=_build_definition(),
        diff_summary=[_node_diff(node_id=DEFINITION_ID, kind="CoreGeneratorDefinition", element_names=["targets"])],
    )

    assert outcome.matched is True
    assert outcome.trigger is not None
    assert outcome.trigger.code is RegenerationReason.DEFINITION_CHANGED
    assert outcome.reason == (
        f"Definition device-generator ({DEFINITION_ID}): definition node was modified (targets) - "
        f"all instances of this definition will regenerate."
    )


def test_transform_changed_reason_uses_generator_source_noun() -> None:
    """The precise-closure path names the intersecting file and uses the ``generator source`` noun."""
    outcome = transform_changed(
        definition=_build_definition(dependencies=["generators/device/device.py"], dependencies_complete=True),
        repo_diff=_build_repo_diff(files_changed=["generators/device/device.py"]),
    )

    assert outcome.matched is True
    assert outcome.trigger is not None
    assert outcome.trigger.code is RegenerationReason.FILE_IN_CLOSURE
    assert outcome.reason == (
        "Definition device-generator: file generators/device/device.py changed and is in this generator source's "
        "dependency closure - all instances will regenerate."
    )


def test_transform_changed_reason_explains_the_legacy_fallback_for_generators() -> None:
    """A pre-feature generator (``dependencies=null``) explains the self-heal-on-re-import path."""
    outcome = transform_changed(
        definition=_build_definition(dependencies=None, dependencies_complete=None),
        repo_diff=_build_repo_diff(files_changed=["any/path.txt"]),
    )

    assert outcome.matched is True
    assert outcome.trigger is not None
    assert outcome.trigger.code is RegenerationReason.DEPENDENCIES_NULL
    assert outcome.reason == (
        "Definition device-generator: generator source was imported before this feature deployed "
        "(dependencies=null) - falling back to regenerate-on-any-file-change. The next re-import of this "
        "generator source will populate its dependency closure."
    )


def test_transform_changed_reason_explains_the_incomplete_closure_fallback_for_generators() -> None:
    """An incomplete closure (``dependencies_complete=False``) names the cause as the safety fallback."""
    outcome = transform_changed(
        definition=_build_definition(dependencies=["generators/device/device.py"], dependencies_complete=False),
        repo_diff=_build_repo_diff(files_changed=["unrelated/file.md"]),
    )

    assert outcome.matched is True
    assert outcome.trigger is not None
    assert outcome.trigger.code is RegenerationReason.DEPENDENCIES_INCOMPLETE
    assert outcome.reason == (
        "Definition device-generator: generator source dependency closure is incomplete "
        "(dependencies_complete=False) - falling back to regenerate-on-any-file-change."
    )


def test_non_triggered_generator_predicates_carry_no_reason() -> None:
    """Predicates that do not fire carry no reason, so a non-triggered generator emits nothing.

    This is the not-run side of the diagnostics contract: only the predicate that actually selected a
    generator contributes a log line, and a complete closure no file change intersects stays silent.
    """
    definition = _build_definition(dependencies=["generators/device/device.py"], dependencies_complete=True)

    assert query_changed(definition=definition, diff_summary=[]).reason is None
    assert definition_changed(definition=definition, diff_summary=[]).reason is None
    assert (
        transform_changed(
            definition=definition, repo_diff=_build_repo_diff(files_changed=["transforms/other/main.py"])
        ).reason
        is None
    )
