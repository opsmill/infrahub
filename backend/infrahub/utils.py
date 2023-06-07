import os
from enum import Enum, EnumMeta
from itertools import groupby
from typing import List, Optional
from uuid import uuid4

KWARGS_TO_DROP = ["session"]


def generate_uuid() -> str:
    return str(uuid4())


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


def get_models_dir():
    """Get the directory which stores additional models."""
    here = os.path.abspath(os.path.dirname(__file__))
    models_dir = os.path.join(here, "..", "..", "models")

    return os.path.abspath(models_dir)


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


def find_first_file_in_directory(directory: str) -> Optional[str]:
    top_level_files = os.listdir(directory)
    for filename in top_level_files:
        full_filename = os.path.join(directory, filename)
        if os.path.isfile(full_filename):
            return filename

    return None


def str_to_bool(value: str) -> bool:
    """Convert a String to a Boolean"""

    if isinstance(value, bool):
        return value

    if isinstance(value, int) and value in [0, 1]:
        return bool(value)

    if not isinstance(value, str):
        raise TypeError(f"{value} must be a string")

    MAP = {
        "y": True,
        "yes": True,
        "t": True,
        "true": True,
        "on": True,
        "1": True,
        "n": False,
        "no": False,
        "f": False,
        "false": False,
        "off": False,
        "0": False,
    }
    try:
        return MAP[value.lower()]
    except KeyError as exc:
        raise ValueError(f"{value} can not be converted into a boolean") from exc


class MetaEnum(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)  # pylint: disable=no-value-for-parameter
        except ValueError:
            return False
        return True


class BaseEnum(Enum, metaclass=MetaEnum):
    pass
