import pytest

from tests.unit.core.schema_change.equivalence_cases import COMBINED_LOAD_CASES, EQUIVALENCE_CASES
from tests.unit.core.schema_change.equivalence_cases_kinds import MOVED_TAG_NAMESPACE
from tests.unit.core.schema_change.helpers import CombinedLoad, CombinedLoadCase, assert_same_load_result


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in EQUIVALENCE_CASES])
def test_applied_operations_give_the_direct_load_result_for_the_kinds_of_the_case(
    test_case: CombinedLoadCase, combined_load: CombinedLoad
) -> None:
    owned_kinds = test_case.owned_kinds(base_schema=combined_load.base, result_schema=combined_load.expected.schema)
    assert owned_kinds & set(combined_load.expected.validation.diff.all), (
        "the schema file of the case must change one of its kinds"
    )

    assert_same_load_result(expected=combined_load.expected, actual=combined_load.actual, kinds=owned_kinds)


def test_applied_operations_give_the_direct_load_result_for_every_kind(combined_load: CombinedLoad) -> None:
    assert_same_load_result(expected=combined_load.expected, actual=combined_load.actual)


def test_each_case_of_the_combined_load_has_a_namespace_of_its_own() -> None:
    namespaces = [case.namespace for case in COMBINED_LOAD_CASES] + [MOVED_TAG_NAMESPACE]

    assert sorted({namespace for namespace in namespaces if namespaces.count(namespace) > 1}) == []
