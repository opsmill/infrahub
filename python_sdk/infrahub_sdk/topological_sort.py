from __future__ import annotations

from itertools import chain
from typing import Any, Iterable, Mapping, Sequence


class DependencyCycleExistsError(Exception):
    def __init__(self, cycles: Iterable[Sequence[str]], *args: tuple[Any]) -> None:
        self.cycles = cycles
        super().__init__(*args)

    def get_cycle_strings(self) -> list[str]:
        return [" --> ".join([str(node) for node in cycle]) for cycle in self.cycles]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.get_cycle_strings()})"


def topological_sort(dependency_dict: Mapping[str, Iterable[str]]) -> list[set[str]]:
    if not dependency_dict:
        return []

    missing_dependent_keys = set(chain(*dependency_dict.values())) - set(dependency_dict.keys())

    dependency_dict_to_sort = {k: set(v) for k, v in dependency_dict.items()}
    dependency_dict_to_sort.update({missing_key: set() for missing_key in missing_dependent_keys})

    ordered = []
    while len(dependency_dict_to_sort) > 0:
        nondependant_nodes = {key for key, dependencies in dependency_dict_to_sort.items() if len(dependencies) == 0}
        dependency_dict_to_sort = {
            k: v - nondependant_nodes for k, v in dependency_dict_to_sort.items() if k not in nondependant_nodes
        }
        ordered.append(nondependant_nodes)

        if len(nondependant_nodes) == 0 and len(dependency_dict_to_sort) != 0:
            cycles = get_cycles(dependency_dict_to_sort)
            raise DependencyCycleExistsError(cycles=cycles)
    return ordered


def get_cycles(dependency_dict: Mapping[str, Iterable[str]]) -> list[list[str]]:
    if not dependency_dict:
        return []

    dict_to_check = {**dependency_dict}
    cycles = []

    while dict_to_check:
        start_path = list(dict_to_check.keys())[:1]
        cycles += _get_cycles(dependency_dict=dict_to_check, path=start_path)
    return cycles


def _get_cycles(dependency_dict: dict[str, Iterable[str]], path: list[str]) -> list[list[str]]:
    try:
        next_nodes = dependency_dict.pop(path[-1])
    except KeyError:
        return []
    cycles = []
    for next_node in next_nodes:
        if next_node in path:
            cycles.append(path[path.index(next_node) :] + [next_node])
        else:
            next_cycles = _get_cycles(dependency_dict, path + [next_node])
            if next_cycles:
                cycles += next_cycles
    return cycles
