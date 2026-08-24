from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.merge.selective_regen.fallbacks import (
    dependency_closure_trigger,
    repositories_forcing_full_regeneration,
)
from infrahub.core.regeneration.models import RegenerationReason, RegenerationTrigger
from infrahub.generators.models import ProposedChangeGeneratorDefinition

REPOSITORY_ID = "repo-1"


def _generator_definition(
    *,
    definition_id: str = "def-1",
    repository_id: str = REPOSITORY_ID,
    fingerprint: str | None = "fp",
    dependencies: list[str] | None = None,
    dependencies_complete: bool | None = None,
) -> ProposedChangeGeneratorDefinition:
    return ProposedChangeGeneratorDefinition(
        definition_id=definition_id,
        definition_name=definition_id,
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
        repository_id=repository_id,
        fingerprint=fingerprint,
        dependencies=dependencies,
        dependencies_complete=dependencies_complete,
    )


def test_populated_fingerprint_forces_no_repository() -> None:
    definitions = [_generator_definition(fingerprint="fp")]
    assert repositories_forcing_full_regeneration(definitions=definitions) == {}


def test_null_fingerprint_forces_its_repository() -> None:
    definitions = [_generator_definition(fingerprint=None)]
    forced = repositories_forcing_full_regeneration(definitions=definitions)
    assert set(forced) == {REPOSITORY_ID}
    assert forced[REPOSITORY_ID].code is RegenerationReason.MISSING_FINGERPRINT
    assert forced[REPOSITORY_ID].detail == (
        f"repository {REPOSITORY_ID} has a definition with no computed fingerprint; "
        f"regenerating every definition of the repository"
    )


def test_a_null_fingerprint_definition_escalates_the_whole_repository() -> None:
    definitions = [
        _generator_definition(definition_id="def-null", fingerprint=None),
        _generator_definition(definition_id="def-populated", fingerprint="fp"),
    ]
    forced = repositories_forcing_full_regeneration(definitions=definitions)
    assert set(forced) == {REPOSITORY_ID}


@dataclass(frozen=True, kw_only=True)
class DependencyCase:
    name: str
    dependencies: list[str] | None
    dependencies_complete: bool | None
    expected: RegenerationTrigger | None


DEPENDENCY_CASES = [
    DependencyCase(
        name="null_dependencies_force",
        dependencies=None,
        dependencies_complete=None,
        expected=RegenerationTrigger(
            code=RegenerationReason.DEPENDENCIES_NULL,
            detail=(
                "def-1: generator source dependency closure is not computed "
                "(dependencies=null); regenerating all instances"
            ),
        ),
    ),
    DependencyCase(
        name="incomplete_dependencies_force",
        dependencies=["a.py"],
        dependencies_complete=False,
        expected=RegenerationTrigger(
            code=RegenerationReason.DEPENDENCIES_INCOMPLETE,
            detail=(
                "def-1: generator source dependency closure is incomplete "
                "(dependencies_complete=False); regenerating all instances"
            ),
        ),
    ),
    DependencyCase(
        name="complete_dependencies_do_not_force",
        dependencies=["a.py"],
        dependencies_complete=True,
        expected=None,
    ),
    DependencyCase(
        name="complete_but_empty_dependencies_do_not_force",
        dependencies=[],
        dependencies_complete=True,
        expected=None,
    ),
]


@pytest.mark.parametrize("case", DEPENDENCY_CASES, ids=lambda case: case.name)
def test_dependency_closure_trigger(case: DependencyCase) -> None:
    definition = _generator_definition(dependencies=case.dependencies, dependencies_complete=case.dependencies_complete)
    assert dependency_closure_trigger(definition) == case.expected
