import os
from distutils.dir_util import copy_tree
from enum import Enum, EnumMeta
from itertools import groupby
from typing import Any, List, Optional
from uuid import UUID


def is_valid_uuid(value: Any) -> bool:
    """Check if the input is a valid UUID."""
    try:
        UUID(str(value))
        return True
    except ValueError:
        return False


def duplicates(input_list: list) -> list:
    """Identify and return all the duplicates in a list."""

    dups = []
    for x, y in groupby(sorted(input_list)):
        #  list(y) returns all the occurences of item x
        if len(list(y)) > 1:
            dups.append(x)

    return dups


def intersection(list1, list2) -> list:
    """Calculate the intersection between 2 lists."""
    return list(set(list1) & set(list2))


def get_fixtures_dir():
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = os.path.abspath(os.path.dirname(__file__))
    fixtures_dir = os.path.join(here, "..", "tests", "fixtures")

    return os.path.abspath(fixtures_dir)


def deep_merge_dict(dicta: dict, dictb: dict, path: Optional[List] = None):
    """Deep Merge dictionnary B into Dictionnary A.
    Code is inspired by https://stackoverflow.com/a/7205107
    """
    if path is None:
        path = []
    for key in dictb:
        if key in dicta:
            if isinstance(dicta[key], dict) and isinstance(dictb[key], dict):
                deep_merge_dict(dicta[key], dictb[key], path + [str(key)])
            elif dicta[key] == dictb[key]:
                pass
            else:
                raise ValueError("Conflict at %s" % ".".join(path + [str(key)]))
        else:
            dicta[key] = dictb[key]
    return dicta


def copy_project_to_tmp_dir(project_name):
    """Function used to copy data to isolated file system."""
    fixtures_dir = get_fixtures_dir()
    copy_tree(os.path.join(fixtures_dir, project_name), "./")


class MetaEnum(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)  # pylint: disable=no-value-for-parameter
        except ValueError:
            return False
        return True


class BaseEnum(Enum, metaclass=MetaEnum):
    pass
