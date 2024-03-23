import pytest

from infrahub_sdk.topological_sort import DependencyCycleExistsError, topological_sort


def test_topological_sort_empty():
    assert topological_sort(dict()) == []


def test_topological_sort_with_cycle_raises_error():
    dependencies = {0: [1, 2], 1: [2], 2: [0]}

    with pytest.raises(DependencyCycleExistsError) as exc:
        topological_sort(dependencies)

    assert [0, 1, 2, 0] in exc.value.cycles or [0, 2, 0] in exc.value.cycles


def test_topological_sort_with_two_separate_cycles_raises_error():
    dependencies = {0: [1, 2], 1: [2], 2: [0], 4: [5, 6], 5: [1, 6], 6: [4]}

    with pytest.raises(DependencyCycleExistsError) as exc:
        topological_sort(dependencies)

    assert [0, 1, 2, 0] in exc.value.cycles or [0, 2, 0] in exc.value.cycles
    assert [4, 5, 6, 4] in exc.value.cycles or [4, 6, 4] in exc.value.cycles


def test_topological_sort():
    dependencies = {0: [1, 2], 1: [2]}

    ordered = topological_sort(dependencies)

    assert ordered == [{2}, {1}, {0}]


def test_topological_sort_2():
    dependencies = {
        0: [1, 2],
        1: [2],
        2: [3],
    }

    ordered = topological_sort(dependencies)

    assert ordered == [{3}, {2}, {1}, {0}]


def test_topological_sort_disjoint():
    dependencies = {
        "a": ["b", "c"],
        "b": ["c"],
        "c": ["d"],
        "e": ["f", "g"],
        "f": ["g"],
        "g": ["h"],
    }

    ordered = topological_sort(dependencies)

    assert ordered == [{"h", "d"}, {"g", "c"}, {"b", "f"}, {"a", "e"}]


def test_topological_sort_disjoint_2():
    dependencies = {
        "a": ["b"],
        "c": ["d"],
        "e": ["f"],
    }

    ordered = topological_sort(dependencies)

    assert ordered == [{"b", "d", "f"}, {"a", "c", "e"}]


def test_topological_sort_binary_tree():
    """
                a
        b               c
      d   e         f       g
    hi            j   k
                  lm
    """
    dependencies = {
        "a": ["b", "c"],
        "b": ["d", "e"],
        "c": ["f", "g"],
        "d": ["h", "i"],
        "f": ["j", "k"],
        "j": ["l", "m"],
    }

    ordered = topological_sort(dependencies)

    assert ordered == [{"l", "m", "h", "i", "e", "g", "k"}, {"j", "d"}, {"b", "f"}, {"c"}, {"a"}]
