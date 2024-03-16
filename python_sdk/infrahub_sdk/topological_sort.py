from itertools import chain
from typing import Iterable, List, Mapping, Set


class DependencyCycleExistsError(Exception):
    ...


def topological_sort(dependency_dict: Mapping[str, Iterable[str]]) -> List[Set[str]]:
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
            raise DependencyCycleExistsError(dependency_dict_to_sort)
    return ordered
