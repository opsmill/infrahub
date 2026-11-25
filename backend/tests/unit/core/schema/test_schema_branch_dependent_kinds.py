from copy import deepcopy
from dataclasses import dataclass

import pytest

from infrahub.core.schema.schema_branch import SchemaBranch
from tests.helpers.schema.car import CAR
from tests.helpers.schema.device import INTERFACE


def _schema_branch() -> SchemaBranch:
    interface = deepcopy(INTERFACE)
    interface.used_by = ["TestingPhysicalInterface", "TestingVirtualInterface"]
    branch = SchemaBranch(cache={}, name="test")
    branch.set(name=CAR.kind, schema=deepcopy(CAR))
    branch.set(name=interface.kind, schema=interface)
    return branch


@dataclass(frozen=True, kw_only=True)
class DependentKindsCase:
    name: str
    kind: str
    expected: frozenset[str]


DEPENDENT_KINDS_CASES: list[DependentKindsCase] = [
    DependentKindsCase(
        name="node",
        kind="TestingCar",
        expected=frozenset({"TestingCar", "ProfileTestingCar", "TemplateTestingCar"}),
    ),
    DependentKindsCase(
        name="generic",
        kind="TestingInterface",
        expected=frozenset(
            {
                "TestingInterface",
                "ProfileTestingInterface",
                "TemplateTestingInterface",
                "TestingPhysicalInterface",
                "ProfileTestingPhysicalInterface",
                "TemplateTestingPhysicalInterface",
                "TestingVirtualInterface",
                "ProfileTestingVirtualInterface",
                "TemplateTestingVirtualInterface",
            }
        ),
    ),
    DependentKindsCase(name="absent_kind", kind="TestingMissing", expected=frozenset()),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in DEPENDENT_KINDS_CASES])
def test_get_dependent_kinds(case: DependentKindsCase) -> None:
    assert _schema_branch().get_dependent_kinds(name=case.kind) == case.expected
