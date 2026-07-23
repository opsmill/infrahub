from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.merge.selective_regen.definition_selector.base import DefinitionSelectorBase
from infrahub.core.merge.selective_regen.fallbacks import repositories_forcing_full_regeneration
from infrahub.core.merge.selective_regen.gate import DefinitionGate
from infrahub.core.merge.selective_regen.impacted import ImpactedSubscriberResolver
from infrahub.core.merge.selective_regen.models import GateResult, LoadedDefinition
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

TARGET_BRANCH = "main"


async def _run_select(selector: _StubSelector) -> list[RequestGeneratorDefinitionRun]:
    loaded = await selector.load_definitions(target_branch=TARGET_BRANCH)
    forced = repositories_forcing_full_regeneration(definitions=[entry.definition for entry in loaded])
    return await selector.select(
        loaded_definitions=loaded,
        forced_repositories=forced,
        diff_summary=[],
        target_branch=TARGET_BRANCH,
        modified_kinds=[],
    )


async def _select_with_rejecting_gate(
    *definitions: ProposedChangeGeneratorDefinition,
) -> list[RequestGeneratorDefinitionRun]:
    selector = _StubSelector(
        gate=_StubGate(
            {
                definition.definition_name: GateResult(regenerate_all_members=False, selected=False)
                for definition in definitions
            }
        ),
        impacted_resolver=_StubImpactedResolver([]),
        definitions=list(definitions),
        member_ids=["m1", "m2"],
        subscriber_by_member={"m1": "s1", "m2": "s2"},
    )
    return await _run_select(selector)


def _generator_definition(
    *,
    name: str = "gen",
    group_id: str = "grp-1",
    dependencies: list[str] | None = None,
    dependencies_complete: bool | None = True,
    fingerprint: str | None = "fp-1",
) -> ProposedChangeGeneratorDefinition:
    return ProposedChangeGeneratorDefinition(
        definition_id=f"def-{name}",
        definition_name=name,
        query_name="q",
        convert_query_response=False,
        class_name="C",
        file_path="gen.py",
        group_id=group_id,
        parameters={},
        execute_in_proposed_change=False,
        execute_after_merge=True,
        query_id="q-1",
        query_models=[],
        query_payload="query {}",
        repository_id="repo-1",
        dependencies=dependencies if dependencies is not None else [],
        dependencies_complete=dependencies_complete,
        fingerprint=fingerprint,
    )


class _StubGate(DefinitionGate):
    """A gate whose verdict is fixed per definition name, bypassing diff evaluation."""

    def __init__(self, results: dict[str, GateResult]) -> None:
        self.results = results

    def evaluate(
        self, *, definition: object, diff_summary: list[NodeDiff], modified_kinds: list[str], group_id: str
    ) -> GateResult:
        return self.results[definition.definition_name]  # type: ignore[attr-defined]


class _StubImpactedResolver(ImpactedSubscriberResolver):
    """A resolver that returns a fixed list of impacted subscriber ids."""

    def __init__(self, impacted: list[str]) -> None:
        self.impacted = impacted

    async def resolve(
        self,
        *,
        query_payload: str,
        diff_summary: list[NodeDiff],
        target_branch: str,
        subscriber_kind: str,
        existing_subscribers: list[str],
    ) -> list[str]:
        return self.impacted


class _StubSelector(DefinitionSelectorBase[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun]):
    """Drives the template's ``select`` with canned definitions, group members and subscribers.

    The kind-specific hooks return injected data so the test exercises only the shared template.
    """

    subscriber_kind = "TestSubscriber"

    def __init__(
        self,
        *,
        gate: DefinitionGate,
        impacted_resolver: ImpactedSubscriberResolver,
        definitions: list[ProposedChangeGeneratorDefinition],
        member_ids: list[str],
        subscriber_by_member: dict[str, str],
    ) -> None:
        self.gate = gate
        self.impacted_resolver = impacted_resolver
        self.log = logging.getLogger("test_base")
        self._definitions = definitions
        self._member_ids = member_ids
        self._subscriber_by_member = subscriber_by_member

    async def load_definitions(
        self, *, target_branch: str
    ) -> list[LoadedDefinition[ProposedChangeGeneratorDefinition]]:
        return [
            LoadedDefinition(definition=definition, group_id=definition.group_id) for definition in self._definitions
        ]

    async def _map_subscribers_by_member(
        self, *, definition: ProposedChangeGeneratorDefinition, target_branch: str
    ) -> dict[str, str]:
        return self._subscriber_by_member

    async def _fetch_member_ids(
        self, *, definition: ProposedChangeGeneratorDefinition, target_branch: str
    ) -> list[str]:
        return self._member_ids

    def _should_render(self, *, subscriber_id: str | None, regenerate_all_members: bool, impacted: list[str]) -> bool:
        return not subscriber_id or regenerate_all_members or subscriber_id in impacted

    def _build_request(
        self, *, definition: ProposedChangeGeneratorDefinition, target_branch: str, members: list[str]
    ) -> RequestGeneratorDefinitionRun:
        return RequestGeneratorDefinitionRun(
            branch=target_branch, generator_definition=definition, target_members=members
        )


@dataclass
class SelectCase:
    name: str
    selected: bool
    regenerate_all_members: bool
    member_ids: list[str]
    subscriber_by_member: dict[str, str]
    impacted: list[str]
    expected_target_members: list[list[str]]


SELECT_CASES = [
    SelectCase(
        name="gate_rejects_yields_no_request",
        selected=False,
        regenerate_all_members=False,
        member_ids=["m1", "m2"],
        subscriber_by_member={},
        impacted=[],
        expected_target_members=[],
    ),
    SelectCase(
        name="regenerate_all_members_renders_all_as_empty_filter",
        selected=True,
        regenerate_all_members=True,
        member_ids=["m1", "m2"],
        subscriber_by_member={"m1": "s1", "m2": "s2"},
        impacted=[],
        expected_target_members=[[]],
    ),
    SelectCase(
        name="new_members_without_subscribers_render_all",
        selected=True,
        regenerate_all_members=False,
        member_ids=["m1", "m2"],
        subscriber_by_member={},
        impacted=[],
        expected_target_members=[[]],
    ),
    SelectCase(
        name="only_impacted_subscribers_narrow_the_filter",
        selected=True,
        regenerate_all_members=False,
        member_ids=["m1", "m2"],
        subscriber_by_member={"m1": "s1", "m2": "s2"},
        impacted=["s1"],
        expected_target_members=[["m1"]],
    ),
    SelectCase(
        name="no_member_renders_drops_the_definition",
        selected=True,
        regenerate_all_members=False,
        member_ids=["m1", "m2"],
        subscriber_by_member={"m1": "s1", "m2": "s2"},
        impacted=[],
        expected_target_members=[],
    ),
]


@pytest.mark.parametrize("case", SELECT_CASES, ids=lambda case: case.name)
async def test_select_narrows_and_drops(case: SelectCase) -> None:
    definition = _generator_definition()
    selector = _StubSelector(
        gate=_StubGate(
            {
                definition.definition_name: GateResult(
                    regenerate_all_members=case.regenerate_all_members, selected=case.selected
                )
            }
        ),
        impacted_resolver=_StubImpactedResolver(case.impacted),
        definitions=[definition],
        member_ids=case.member_ids,
        subscriber_by_member=case.subscriber_by_member,
    )

    requests = await _run_select(selector)

    assert [request.target_members for request in requests] == case.expected_target_members


@dataclass
class ForceCase:
    name: str
    fingerprint: str | None
    dependencies_complete: bool | None


FORCE_CASES = [
    ForceCase(name="null_fingerprint_forces_selection", fingerprint=None, dependencies_complete=True),
    ForceCase(name="incomplete_dependencies_force_selection", fingerprint="fp-1", dependencies_complete=False),
]


@pytest.mark.parametrize("case", FORCE_CASES, ids=lambda case: case.name)
async def test_untrusted_signal_forces_selection_over_a_rejecting_gate(case: ForceCase) -> None:
    # The gate rejects and no member has an impacted subscriber, yet the untrusted change signal
    # must still regenerate every member (empty filter = all) rather than drop the definition.
    definition = _generator_definition(fingerprint=case.fingerprint, dependencies_complete=case.dependencies_complete)
    requests = await _select_with_rejecting_gate(definition)
    assert [request.target_members for request in requests] == [[]]


async def test_null_fingerprint_forces_a_populated_sibling_in_the_same_repository() -> None:
    # The escalation is computed across all loaded definitions, so a definition with a populated
    # fingerprint is force-regenerated because a sibling of the same repository has none — even
    # though the gate rejects both. A regression scoping the forcing per-definition would silently
    # drop the populated sibling.
    null_fp = _generator_definition(name="null-fp", fingerprint=None)
    populated_fp = _generator_definition(name="populated-fp", fingerprint="fp-1")
    assert null_fp.repository_id == populated_fp.repository_id

    requests = await _select_with_rejecting_gate(null_fp, populated_fp)

    assert sorted(request.generator_definition.definition_name for request in requests) == [
        "null-fp",
        "populated-fp",
    ]
    assert [request.target_members for request in requests] == [[], []]


async def test_untrusted_dependency_closure_forces_only_its_own_definition() -> None:
    untrusted = _generator_definition(name="untrusted", dependencies=["a.py"], dependencies_complete=False)
    trusted = _generator_definition(name="trusted", dependencies=["a.py"], dependencies_complete=True)
    assert untrusted.repository_id == trusted.repository_id

    requests = await _select_with_rejecting_gate(untrusted, trusted)

    # Only the untrusted definition regenerates, and it regenerates every member (empty filter); the
    # trusted sibling is dropped because nothing selected or forced it.
    assert [request.generator_definition.definition_name for request in requests] == ["untrusted"]
    assert [request.target_members for request in requests] == [[]]


async def test_select_processes_each_definition_independently() -> None:
    selected = _generator_definition(name="selected")
    rejected = _generator_definition(name="rejected")
    selector = _StubSelector(
        gate=_StubGate(
            {
                selected.definition_name: GateResult(regenerate_all_members=True, selected=True),
                rejected.definition_name: GateResult(regenerate_all_members=False, selected=False),
            }
        ),
        impacted_resolver=_StubImpactedResolver([]),
        definitions=[selected, rejected],
        member_ids=["m1"],
        subscriber_by_member={},
    )

    requests = await _run_select(selector)

    assert [request.generator_definition.definition_name for request in requests] == ["selected"]
