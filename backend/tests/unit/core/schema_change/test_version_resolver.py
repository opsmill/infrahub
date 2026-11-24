from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from infrahub.core.branch import Branch
from infrahub.core.schema_change.repository import AppliedSchemaChangeVersion
from infrahub.core.schema_change.version_resolver import SchemaChangeVersion, SchemaChangeVersionResolver
from infrahub.core.timestamp import Timestamp
from tests.unit.core.schema_change.helpers import (
    GET_HIGHEST_APPLIED_VERSION,
    GET_HIGHEST_APPLIED_VERSION_AT,
    RecordingSchemaChangeRepository,
    SchemaChangeRepositoryCall,
)

MAIN = "main"
FEATURE = "feature"
BRANCHED_FROM = "2026-03-02T10:15:00Z"
MAIN_SCHEMA_CHANGE_ID = "b6e1d9a3-0c4f-4e72-8a5d-2f7c9b1e3d60"
FEATURE_SCHEMA_CHANGE_ID = "e47a2c5b-9d1e-4f36-b8c0-6a3d1f5e7b92"


def _highest_version_call(branch: str) -> SchemaChangeRepositoryCall:
    return SchemaChangeRepositoryCall(method=GET_HIGHEST_APPLIED_VERSION, arguments={"branch": branch})


MAIN_AT_BRANCH_CREATION_CALL = SchemaChangeRepositoryCall(
    method=GET_HIGHEST_APPLIED_VERSION_AT, arguments={"branch": MAIN, "at": Timestamp(BRANCHED_FROM)}
)


@dataclass(frozen=True)
class ResolveNextCase:
    name: str
    branch: str
    expected: SchemaChangeVersion
    expected_calls: list[SchemaChangeRepositoryCall]
    highest_versions: dict[str, AppliedSchemaChangeVersion] = field(default_factory=dict)
    highest_versions_at: dict[str, AppliedSchemaChangeVersion] = field(default_factory=dict)
    """The highest applied version of a branch among those applied at or before the time read."""


RESOLVE_NEXT_CASES = [
    ResolveNextCase(
        name="main_without_schema_change_gives_version_1_without_parent",
        branch=MAIN,
        expected=SchemaChangeVersion(version=1, parent_id=None),
        expected_calls=[_highest_version_call(MAIN)],
    ),
    ResolveNextCase(
        name="main_gives_its_highest_version_plus_1_with_that_schema_change_as_parent",
        branch=MAIN,
        highest_versions={MAIN: AppliedSchemaChangeVersion(schema_change_id=MAIN_SCHEMA_CHANGE_ID, version=3)},
        expected=SchemaChangeVersion(version=4, parent_id=MAIN_SCHEMA_CHANGE_ID),
        expected_calls=[_highest_version_call(MAIN)],
    ),
    ResolveNextCase(
        name="branch_with_an_applied_schema_change_numbers_after_its_own_without_reading_main",
        branch=FEATURE,
        highest_versions={
            MAIN: AppliedSchemaChangeVersion(schema_change_id=MAIN_SCHEMA_CHANGE_ID, version=7),
            FEATURE: AppliedSchemaChangeVersion(schema_change_id=FEATURE_SCHEMA_CHANGE_ID, version=3),
        },
        expected=SchemaChangeVersion(version=4, parent_id=FEATURE_SCHEMA_CHANGE_ID),
        expected_calls=[_highest_version_call(FEATURE)],
    ),
    ResolveNextCase(
        name="branch_without_schema_change_numbers_after_main_at_its_creation",
        branch=FEATURE,
        highest_versions={MAIN: AppliedSchemaChangeVersion(schema_change_id=FEATURE_SCHEMA_CHANGE_ID, version=7)},
        highest_versions_at={MAIN: AppliedSchemaChangeVersion(schema_change_id=MAIN_SCHEMA_CHANGE_ID, version=2)},
        expected=SchemaChangeVersion(version=3, parent_id=MAIN_SCHEMA_CHANGE_ID),
        expected_calls=[_highest_version_call(FEATURE), MAIN_AT_BRANCH_CREATION_CALL],
    ),
    ResolveNextCase(
        name="branch_created_before_any_schema_change_of_main_gives_version_1_without_parent",
        branch=FEATURE,
        highest_versions={MAIN: AppliedSchemaChangeVersion(schema_change_id=MAIN_SCHEMA_CHANGE_ID, version=1)},
        expected=SchemaChangeVersion(version=1, parent_id=None),
        expected_calls=[_highest_version_call(FEATURE), MAIN_AT_BRANCH_CREATION_CALL],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RESOLVE_NEXT_CASES])
async def test_resolve_next(test_case: ResolveNextCase) -> None:
    repository = RecordingSchemaChangeRepository(
        highest_versions=test_case.highest_versions, highest_versions_at=test_case.highest_versions_at
    )
    resolver = SchemaChangeVersionResolver(repository=repository, default_branch_name=MAIN)

    version = await resolver.resolve_next(branch=Branch(name=test_case.branch, branched_from=BRANCHED_FROM))

    assert version == test_case.expected
    assert repository.calls == test_case.expected_calls
